"""Text, timestamp, cookie, and console-output helpers."""

from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional


def configure_console_encoding() -> None:
    """Use UTF-8 on Windows consoles so Chinese output is readable."""
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def clean_text(value: Any) -> str:
    """Strip HTML tags and normalize whitespace without losing line breaks."""
    if value is None:
        return ""
    text = str(value)
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def format_timestamp(timestamp: Any) -> str:
    """Convert a Bilibili Unix timestamp to a readable local string."""
    try:
        value = int(float(timestamp))
        if value > 10_000_000_000:
            value //= 1000
        if value > 0:
            return datetime.fromtimestamp(value).isoformat(
                sep=" ", timespec="seconds"
            )
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    return ""


def sanitize_filename(value: str) -> str:
    """Make a keyword safe for use in a Windows-compatible filename."""
    value = value.strip()
    if not value:
        return "bilibili"
    value = re.sub(r'[<>:"/\\|?*]', "_", value)
    value = re.sub(r"\s+", "_", value)
    return value[:80].rstrip("._")


def parse_cookie(cookie_input: Optional[str]) -> str:
    """Read a raw cookie string or a Netscape-format cookie file."""
    if not cookie_input:
        return ""

    cookie_path = Path(cookie_input).expanduser()
    if cookie_path.is_file():
        cookie_input = cookie_path.read_text(encoding="utf-8", errors="ignore")

    cookie_input = cookie_input.strip()
    if cookie_input.startswith("#"):
        pairs: List[str] = []
        for line in cookie_input.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) >= 7 and fields[0].startswith("."):
                pairs.append(f"{fields[5]}={fields[6]}")
        return "; ".join(pairs)

    return cookie_input
