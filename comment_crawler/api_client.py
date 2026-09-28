"""HTTP client and high-level Bilibili data fetching."""

from __future__ import annotations

import hashlib
import re
import time
from itertools import count
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlencode
from xml.etree import ElementTree

try:
    import requests
except ImportError as exc:  # pragma: no cover - checked before importing
    raise SystemExit(
        "Missing dependency 'requests'. Install it with: pip install requests"
    ) from exc

from config import (
    COMMENT_WEB_LOCATION,
    COMMENT_URL,
    COMMENT_WBI_URL,
    DANMAKU_SEG_URL,
    DANMAKU_URL,
    DANMAKU_VIEW_URL,
    MIXIN_KEY_ENC_TAB,
    NAV_URL,
    PAGELIST_URL,
    RISK_CODES,
    SEARCH_URL,
    SEARCH_WBI_URL,
    USER_AGENT,
)
from errors import ApiError, RiskControlError
from protobuf import parse_danmaku_segment, parse_danmaku_view
from utils import clean_text, format_timestamp, parse_cookie


class BilibiliClient:
    """Session wrapper for Bilibili's public JSON/XML/protobuf APIs."""

    def __init__(
        self,
        cookie: Optional[str] = None,
        proxy: Optional[str] = None,
        delay: float = 0.8,
        timeout: float = 15.0,
        retries: int = 3,
    ) -> None:
        self.delay = max(0.0, delay)
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Referer": "https://www.bilibili.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )

        cookie_value = parse_cookie(cookie)
        if cookie_value:
            for item in cookie_value.split(";"):
                if "=" in item:
                    key, value = item.split("=", 1)
                    self.session.cookies.set(key.strip(), value.strip())

        if proxy:
            self.session.proxies.update({"http": proxy, "https": proxy})

        self._warm_guest_session()
        self._wbi_keys: Optional[tuple[str, str]] = None
        self._last_request_time = 0.0

    def _warm_guest_session(self) -> None:
        """Let Bilibili set anonymous tracking cookies before API calls."""
        if "buvid3" in self.session.cookies or "buvid4" in self.session.cookies:
            return
        try:
            self.session.get(
                "https://www.bilibili.com/",
                timeout=self.timeout,
                allow_redirects=True,
            )
        except requests.RequestException:
            pass

    def _wait_for_rate_limit(self) -> None:
        if self.delay <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        use_wbi: bool = False,
        raw: bool = False,
    ) -> Any:
        request_params = dict(params or {})
        if use_wbi:
            request_params = self._sign_wbi(request_params)

        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            self._wait_for_rate_limit()
            self._last_request_time = time.monotonic()
            try:
                response = self.session.get(
                    url,
                    params=request_params,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                if response.status_code in (403, 412, 429):
                    raise RiskControlError(
                        f"HTTP {response.status_code} from {url}"
                    )
                response.raise_for_status()
                if raw:
                    return response
                return response.json()
            except RiskControlError:
                raise
            except (requests.RequestException, ValueError, ApiError) as exc:
                last_error = exc
                if isinstance(exc, ApiError) or attempt >= self.retries:
                    break
                time.sleep(min(4.0, 0.8 * (2**attempt)))

        raise ApiError(f"Request failed after retries: {url}: {last_error}")

    def _get_wbi_keys(self) -> tuple[str, str]:
        if self._wbi_keys:
            return self._wbi_keys

        payload = self._request(NAV_URL)
        if not isinstance(payload, dict):
            raise ApiError("Unexpected nav response from Bilibili")
        data = payload.get("data") or {}
        wbi_img = data.get("wbi_img") or {}
        img_url = wbi_img.get("img_url") or ""
        sub_url = wbi_img.get("sub_url") or ""

        def extract_key(url: str) -> str:
            match = re.search(r"/([^/]+)\.png$", url)
            return match.group(1) if match else ""

        img_key = extract_key(img_url)
        sub_key = extract_key(sub_url)
        if not img_key or not sub_key:
            raise ApiError(
                "Could not obtain Bilibili WBI keys. Try supplying --cookie."
            )

        self._wbi_keys = (img_key, sub_key)
        return self._wbi_keys

    @staticmethod
    def _mixin_key(original: str) -> str:
        return "".join(
            original[index]
            for index in MIXIN_KEY_ENC_TAB
            if index < len(original)
        )[:32]

    def _sign_wbi(self, params: Dict[str, Any]) -> Dict[str, Any]:
        img_key, sub_key = self._get_wbi_keys()
        mixin_key = self._mixin_key(img_key + sub_key)
        signed = dict(params)
        signed["wts"] = int(time.time())
        signed = dict(sorted(signed.items()))

        filtered = {}
        for key, value in signed.items():
            text = str(value)
            text = "".join(char for char in text if char not in "!'()*")
            filtered[key] = text

        query = urlencode(filtered)
        signed["w_rid"] = hashlib.md5(
            (query + mixin_key).encode("utf-8")
        ).hexdigest()
        return signed

    def search_videos(
        self,
        keyword: str,
        *,
        max_videos: int = 0,
        max_pages: int = 0,
        order: str = "totalrank",
        published_after: Optional[int] = None,
        published_before: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Search videos and return deduplicated metadata."""
        videos: List[Dict[str, Any]] = []
        seen: set[str] = set()
        used_wbi = False

        for page in count(1):
            if max_pages > 0 and page > max_pages:
                break
            if max_videos > 0 and len(videos) >= max_videos:
                break

            params: Dict[str, Any] = {
                "search_type": "video",
                "keyword": keyword,
                "page": page,
                "page_size": 20,
                "order": order,
            }
            if published_after is not None:
                params["pubtime_begin_s"] = published_after
            if published_before is not None:
                params["pubtime_end_s"] = published_before
            url = SEARCH_WBI_URL if used_wbi else SEARCH_URL
            try:
                payload = self._request(url, params, use_wbi=used_wbi)
            except RiskControlError:
                if not used_wbi:
                    print(
                        f"  Search page {page} hit risk control; retrying with WBI signature.",
                        flush=True,
                    )
                    used_wbi = True
                    payload = self._request(
                        SEARCH_WBI_URL, params, use_wbi=True
                    )
                else:
                    raise

            if isinstance(payload, dict) and payload.get("code") in RISK_CODES:
                if not used_wbi:
                    print(
                        f"  Search page {page} hit risk control; retrying with WBI signature.",
                        flush=True,
                    )
                    used_wbi = True
                    payload = self._request(
                        SEARCH_WBI_URL, params, use_wbi=True
                    )
                else:
                    raise ApiError(
                        f"Search API denied request: {payload.get('message')}"
                    )

            if not isinstance(payload, dict) or payload.get("code") != 0:
                message = (
                    payload.get("message")
                    if isinstance(payload, dict)
                    else "bad response"
                )
                raise ApiError(f"Search API error: {message}")

            data = payload.get("data") or {}
            result = data.get("result") or []
            if not result:
                break

            added = 0
            for item in result:
                bvid = item.get("bvid") or ""
                if not bvid or bvid in seen:
                    continue
                seen.add(bvid)
                videos.append(
                    {
                        "bvid": bvid,
                        "aid": item.get("aid"),
                        "title": clean_text(item.get("title")),
                        "author": clean_text(item.get("author")),
                        "mid": item.get("mid"),
                        "pubdate": item.get("pubdate"),
                        "play": item.get("play", 0),
                        "danmaku_count": item.get("video_review", 0),
                        "review_count": item.get("review", 0),
                    }
                )
                added += 1
                if max_videos > 0 and len(videos) >= max_videos:
                    break

            print(
                f"  Search page {page}: found {len(result)} items, "
                f"added {added}, total {len(videos)}.",
                flush=True,
            )
            if max_videos > 0 and len(videos) >= max_videos:
                break

        return videos

    def get_video_parts(self, bvid: str) -> List[Dict[str, Any]]:
        """Return the cid(s) for a video, including multi-part videos."""
        payload = self._request(PAGELIST_URL, {"bvid": bvid})
        if not isinstance(payload, dict) or payload.get("code") != 0:
            message = (
                payload.get("message")
                if isinstance(payload, dict)
                else "bad response"
            )
            raise ApiError(f"Pagelist API error for {bvid}: {message}")

        data = payload.get("data") or []
        if not isinstance(data, list):
            raise ApiError(f"Pagelist API returned unexpected data for {bvid}")

        parts = []
        for item in data:
            cid = item.get("cid")
            if cid:
                parts.append(
                    {
                        "cid": cid,
                        "page": item.get("page", 0),
                        "part_title": clean_text(item.get("part")),
                        "duration": item.get("duration", 0),
                    }
                )
        return parts

    def fetch_comments(
        self,
        aid: Any,
        *,
        max_comments: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch all root comments and nested replies for an aid."""
        rows: List[Dict[str, Any]] = []
        used_wbi = False
        risk_retries = 0
        page = 0
        pagination_str: Optional[str] = None
        seen_rpids: set[str] = set()

        while True:
            if max_comments > 0 and len(rows) >= max_comments:
                break

            params: Dict[str, Any] = {
                "type": 1,
                "oid": aid,
                "mode": 3,
                "plat": 1,
                "seek_rpid": "",
                "web_location": COMMENT_WEB_LOCATION,
            }
            if pagination_str:
                params["pagination_str"] = pagination_str
            else:
                params["next"] = page

            url = COMMENT_WBI_URL if used_wbi else COMMENT_URL
            try:
                payload = self._request(url, params, use_wbi=used_wbi)
            except RiskControlError:
                if not used_wbi:
                    used_wbi = True
                    continue
                raise

            code = payload.get("code") if isinstance(payload, dict) else None
            if code in RISK_CODES or code == -400:
                if not used_wbi:
                    used_wbi = True
                    continue
                if code == -400 and risk_retries < 2:
                    risk_retries += 1
                    time.sleep(1.0 + risk_retries)
                    continue
                raise ApiError(
                    f"Comment API denied request for aid {aid}: "
                    f"{payload.get('message') if isinstance(payload, dict) else code}"
                )

            if not isinstance(payload, dict) or code != 0:
                message = (
                    payload.get("message")
                    if isinstance(payload, dict)
                    else "bad response"
                )
                raise ApiError(f"Comment API error for aid {aid}: {message}")

            risk_retries = 0
            data = payload.get("data") or {}
            cursor = data.get("cursor") or {}
            replies = data.get("replies") or []
            if not replies:
                break

            for item in self._walk_replies(replies):
                rpid = item["rpid"]
                if rpid in seen_rpids:
                    continue
                seen_rpids.add(rpid)
                rows.append(item)
                if max_comments > 0 and len(rows) >= max_comments:
                    break

            if max_comments > 0 and len(rows) >= max_comments:
                break
            if cursor.get("is_end"):
                break

            pagination_reply = cursor.get("pagination_reply") or {}
            next_offset = pagination_reply.get("next_offset")
            if next_offset:
                pagination_str = str(next_offset)
                continue

            try:
                next_page = int(cursor.get("next", page + 1))
            except (TypeError, ValueError):
                next_page = page + 1
            if next_page <= page:
                break
            page = next_page

        return rows

    @staticmethod
    def _walk_replies(
        replies: Any,
        root_rpid: str = "",
        parent_rpid: str = "",
    ) -> Iterator[Dict[str, Any]]:
        for reply in replies or []:
            if not isinstance(reply, dict):
                continue

            rpid = str(reply.get("rpid", ""))
            if not rpid:
                continue
            current_root = root_rpid or rpid
            member = reply.get("member") or {}
            content = reply.get("content") or {}
            level_info = member.get("level_info") or {}
            row = {
                "rpid": rpid,
                "root_rpid": current_root,
                "parent_rpid": parent_rpid,
                "user_id": member.get("mid", ""),
                "username": clean_text(member.get("uname")),
                "user_level": level_info.get("current_level", ""),
                "message": clean_text(
                    content.get("message") or content.get("device")
                ),
                "like_count": reply.get("like", 0),
                "reply_count": reply.get("rcount", 0),
                "comment_time": format_timestamp(reply.get("ctime")),
                "comment_timestamp": reply.get("ctime", ""),
            }
            yield row
            yield from BilibiliClient._walk_replies(
                reply.get("replies") or [], current_root, rpid
            )

    def fetch_danmaku(
        self,
        cid: Any,
        *,
        max_danmaku: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch danmaku from XML first, then from segments if XML is blocked."""
        try:
            return self._fetch_danmaku_xml(cid, max_danmaku)
        except (ApiError, ElementTree.ParseError):
            return self._fetch_danmaku_segments(cid, max_danmaku)

    def _fetch_danmaku_segments(
        self,
        cid: Any,
        max_danmaku: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch danmaku from the current segmented web player API."""
        try:
            view_response = self._request(
                DANMAKU_VIEW_URL,
                {"type": 1, "oid": cid},
                raw=True,
            )
            view_body = view_response.content
            if view_body in (b"", b"\x10\x01"):
                return []

            segment_count, _ = parse_danmaku_view(view_body)
            if segment_count <= 0:
                raise ApiError(f"No danmaku segment metadata for cid {cid}")

            rows: List[Dict[str, Any]] = []
            empty_streak = 0
            for segment_index in range(1, segment_count + 1):
                if max_danmaku > 0 and len(rows) >= max_danmaku:
                    break

                segment_response = self._request(
                    DANMAKU_SEG_URL,
                    {
                        "type": 1,
                        "oid": cid,
                        "segment_index": segment_index,
                    },
                    raw=True,
                )
                segment_rows = parse_danmaku_segment(segment_response.content)
                remaining = (
                    max_danmaku - len(rows)
                    if max_danmaku > 0
                    else len(segment_rows)
                )
                rows.extend(segment_rows[:remaining])

                if not segment_rows:
                    empty_streak += 1
                    if empty_streak >= 3 and rows:
                        break
                else:
                    empty_streak = 0

            if not rows:
                raise ApiError(f"No segmented danmaku data for cid {cid}")
            return rows
        except (ApiError, ValueError, ElementTree.ParseError) as exc:
            raise ApiError(
                f"All danmaku endpoints failed for cid {cid}: {exc}"
            ) from exc

    def _fetch_danmaku_xml(
        self,
        cid: Any,
        max_danmaku: int = 0,
    ) -> List[Dict[str, Any]]:
        """Fetch danmaku from the older XML endpoint."""
        response = self._request(DANMAKU_URL, {"oid": cid}, raw=True)
        body = response.content
        if not body or b"<" not in body[:512]:
            raise ApiError(
                f"Danmaku endpoint returned non-XML data for cid {cid}"
            )

        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError as exc:
            raise ApiError(
                f"Could not parse danmaku XML for cid {cid}: {exc}"
            ) from exc

        rows: List[Dict[str, Any]] = []
        for node in root.iter("d"):
            if max_danmaku > 0 and len(rows) >= max_danmaku:
                break

            fields = (node.get("p") or "").split(",")
            if len(fields) < 5:
                continue
            rows.append(
                {
                    "time_seconds": fields[0],
                    "mode": fields[1],
                    "font_size": fields[2],
                    "color": fields[3],
                    "send_time": format_timestamp(fields[4]),
                    "send_timestamp": fields[4],
                    "danmaku_pool": fields[5] if len(fields) > 5 else "",
                    "user_hash": fields[6] if len(fields) > 6 else "",
                    "row_id": fields[7] if len(fields) > 7 else "",
                    "text": clean_text(node.text),
                }
            )
        return rows
