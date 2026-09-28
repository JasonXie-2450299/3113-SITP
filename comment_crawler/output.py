"""CSV field definitions and writer helper."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, List


COMMENT_FIELDS = [
    "video_bvid",
    "video_aid",
    "video_title",
    "video_author",
    "video_pubdate",
    "video_play",
    "video_review_count",
    "rpid",
    "root_rpid",
    "parent_rpid",
    "user_id",
    "username",
    "user_level",
    "message",
    "like_count",
    "reply_count",
    "comment_time",
    "comment_timestamp",
]

DANMAKU_FIELDS = [
    "video_bvid",
    "video_aid",
    "video_title",
    "video_author",
    "video_pubdate",
    "video_play",
    "video_review_count",
    "part_page",
    "part_title",
    "cid",
    "time_seconds",
    "mode",
    "font_size",
    "color",
    "send_time",
    "send_timestamp",
    "danmaku_pool",
    "user_hash",
    "row_id",
    "text",
]

VIDEO_METADATA_FIELDS = [
    "video_bvid",
    "video_aid",
    "video_title",
    "video_author",
    "video_pubdate",
    "video_play",
    "video_review_count",
]


def open_csv_writer(
    path: Path,
    fieldnames: List[str],
    *,
    append: bool = False,
) -> tuple[Any, csv.DictWriter]:
    path.parent.mkdir(parents=True, exist_ok=True)
    file = path.open("a" if append else "w", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    if not append or file.tell() == 0:
        writer.writeheader()
    return file, writer
