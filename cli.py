"""Command-line interface and crawl orchestration."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from api_client import BilibiliClient
from errors import ApiError
from output import (
    COMMENT_FIELDS,
    DANMAKU_FIELDS,
    VIDEO_METADATA_FIELDS,
    open_csv_writer,
)
from utils import configure_console_encoding, format_timestamp, sanitize_filename


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search Bilibili videos by keyword and save comments/danmaku to CSV."
    )
    parser.add_argument("keyword", help="Keyword used to search Bilibili videos.")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for CSV output (default: current directory).",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=0,
        help="Maximum videos to process; 0 means all search results (default: 0).",
    )
    parser.add_argument(
        "--search-pages",
        type=int,
        default=0,
        help="Maximum search result pages; 0 means keep going until no results.",
    )
    parser.add_argument(
        "--max-comments",
        type=int,
        default=0,
        help="Maximum comments per video; 0 means all available comments.",
    )
    parser.add_argument(
        "--max-danmaku",
        type=int,
        default=0,
        help="Maximum danmaku per video part; 0 means all available danmaku.",
    )
    parser.add_argument(
        "--order",
        default="totalrank",
        choices=["totalrank", "click", "pubdate", "dm", "stow", "scores"],
        help="Bilibili search order (default: totalrank).",
    )
    parser.add_argument(
        "--cookie",
        default=os.environ.get("BILIBILI_COOKIE"),
        help="Cookie string, Netscape cookie file, or BILIBILI_COOKIE env value.",
    )
    parser.add_argument(
        "--proxy",
        default=os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"),
        help="HTTP(S) proxy URL.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay in seconds between requests (default: 0.8).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Request timeout in seconds (default: 15).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retry count for transient network errors (default: 3).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_console_encoding()
    args = build_argument_parser().parse_args(argv)
    keyword = args.keyword.strip()
    if not keyword:
        print("Keyword cannot be empty.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir).expanduser()
    safe_keyword = sanitize_filename(keyword)
    comments_path = output_dir / f"{safe_keyword}_comments.csv"
    danmaku_path = output_dir / f"{safe_keyword}_danmaku.csv"

    client = BilibiliClient(
        cookie=args.cookie,
        proxy=args.proxy,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
    )

    print(f"Searching Bilibili for keyword: {keyword}", flush=True)
    try:
        videos = client.search_videos(
            keyword,
            max_videos=args.max_videos,
            max_pages=args.search_pages,
            order=args.order,
        )
    except ApiError as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1

    if not videos:
        print("No videos found.", flush=True)
        return 0

    comments_file, comments_writer = open_csv_writer(
        comments_path, COMMENT_FIELDS
    )
    danmaku_file, danmaku_writer = open_csv_writer(
        danmaku_path, DANMAKU_FIELDS
    )

    empty_metadata = {field: "" for field in VIDEO_METADATA_FIELDS}

    print(f"Found {len(videos)} video(s). Output:", flush=True)
    print(f"  comments: {comments_path}", flush=True)
    print(f"  danmaku:  {danmaku_path}", flush=True)

    total_comments = 0
    total_danmaku = 0
    try:
        for index, video in enumerate(videos, 1):
            bvid = str(video.get("bvid") or "")
            aid = video.get("aid")
            title = str(video.get("title") or "")
            print(
                f"[{index}/{len(videos)}] {bvid} - {title[:50]}",
                flush=True,
            )

            metadata = dict(empty_metadata)
            metadata.update(
                {
                    "video_bvid": bvid,
                    "video_aid": aid,
                    "video_title": title,
                    "video_author": video.get("author", ""),
                    "video_pubdate": format_timestamp(video.get("pubdate")),
                    "video_play": video.get("play", ""),
                    "video_review_count": video.get("review_count", ""),
                }
            )

            if aid:
                try:
                    comments = client.fetch_comments(
                        aid, max_comments=args.max_comments
                    )
                except ApiError as exc:
                    print(
                        f"  Comments failed: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    comments = []
                for row in comments:
                    comments_writer.writerow({**metadata, **row})
                comments_file.flush()
                total_comments += len(comments)
                print(f"  Comments: {len(comments)}", flush=True)
            else:
                print("  Comments: skipped (no aid)", flush=True)

            try:
                parts = client.get_video_parts(bvid)
            except ApiError as exc:
                print(f"  Danmaku skipped: {exc}", file=sys.stderr, flush=True)
                parts = []

            if not parts:
                print("  Danmaku: skipped (no cid)", flush=True)

            for part in parts:
                try:
                    danmaku = client.fetch_danmaku(
                        part["cid"], max_danmaku=args.max_danmaku
                    )
                except ApiError as exc:
                    print(
                        f"  Danmaku failed for part {part.get('page')}: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    danmaku = []
                for row in danmaku:
                    danmaku_writer.writerow(
                        {
                            **metadata,
                            "part_page": part.get("page", ""),
                            "part_title": part.get("part_title", ""),
                            "cid": part.get("cid", ""),
                            **row,
                        }
                    )
                danmaku_file.flush()
                total_danmaku += len(danmaku)
                print(
                    f"  Part {part.get('page')}: danmaku {len(danmaku)}",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("\nInterrupted. Partial CSV data was saved.", flush=True)
    finally:
        comments_file.close()
        danmaku_file.close()

    print("\nDone.", flush=True)
    print(f"Videos processed: {len(videos)}", flush=True)
    print(f"Comments saved: {total_comments}", flush=True)
    print(f"Danmaku saved: {total_danmaku}", flush=True)
    return 0
