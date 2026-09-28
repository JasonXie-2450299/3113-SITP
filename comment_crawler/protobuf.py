"""Minimal protobuf parsing for Bilibili's segmented danmaku API."""

from __future__ import annotations

from typing import Any, Dict, List

from utils import clean_text, format_timestamp


class ProtoReader:
    """Minimal protobuf wire-format reader."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def at_end(self) -> bool:
        return self.pos >= len(self.data)

    def read_varint(self) -> int:
        value = 0
        shift = 0
        while True:
            if self.pos >= len(self.data):
                raise ValueError("Truncated protobuf varint")
            byte = self.data[self.pos]
            self.pos += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value
            shift += 7
            if shift > 70:
                raise ValueError("Invalid protobuf varint")

    def read_field(self) -> tuple[int, int, Any]:
        key = self.read_varint()
        field_number = key >> 3
        wire_type = key & 0x07

        if wire_type == 0:
            value: Any = self.read_varint()
        elif wire_type == 2:
            length = self.read_varint()
            if self.pos + length > len(self.data):
                raise ValueError("Truncated protobuf field")
            value = self.data[self.pos : self.pos + length]
            self.pos += length
        elif wire_type == 1:
            if self.pos + 8 > len(self.data):
                raise ValueError("Truncated protobuf fixed64")
            self.pos += 8
            value = None
        elif wire_type == 5:
            if self.pos + 4 > len(self.data):
                raise ValueError("Truncated protobuf fixed32")
            self.pos += 4
            value = None
        else:
            raise ValueError(f"Unsupported protobuf wire type: {wire_type}")

        return field_number, wire_type, value


def parse_danmaku_view(body: bytes) -> tuple[int, int]:
    """Return (segment_count, total_count) from DmWebViewReply."""
    reader = ProtoReader(body)
    segment_count = 0
    total_count = 0

    while not reader.at_end():
        field_number, wire_type, value = reader.read_field()
        if field_number == 4 and wire_type == 2 and isinstance(value, bytes):
            nested = ProtoReader(value)
            while not nested.at_end():
                nested_field, nested_wire, nested_value = nested.read_field()
                if nested_field == 2 and nested_wire == 0:
                    segment_count = int(nested_value)
        elif field_number == 8 and wire_type == 0:
            total_count = int(value)

    return segment_count, total_count


def parse_danmaku_segment(body: bytes) -> List[Dict[str, Any]]:
    """Parse one DmSegMobileReply message into row dictionaries."""
    reader = ProtoReader(body)
    rows: List[Dict[str, Any]] = []

    while not reader.at_end():
        field_number, wire_type, value = reader.read_field()
        if field_number != 1 or wire_type != 2 or not isinstance(value, bytes):
            continue
        rows.append(parse_danmaku_element(value))

    return rows


def parse_danmaku_element(body: bytes) -> Dict[str, Any]:
    reader = ProtoReader(body)
    progress_ms = 0
    mode = 0
    font_size = 0
    color = 0
    mid_hash = ""
    text = ""
    ctime = 0
    pool = 0
    row_id = ""

    while not reader.at_end():
        field_number, wire_type, value = reader.read_field()
        if wire_type == 0 and isinstance(value, int):
            if field_number == 2:
                progress_ms = value
            elif field_number == 3:
                mode = value
            elif field_number == 4:
                font_size = value
            elif field_number == 5:
                color = value
            elif field_number == 8:
                ctime = value
            elif field_number == 11:
                pool = value
        elif wire_type == 2 and isinstance(value, bytes):
            decoded = value.decode("utf-8", errors="ignore")
            if field_number == 6:
                mid_hash = decoded
            elif field_number == 7:
                text = decoded
            elif field_number == 12:
                row_id = decoded

    seconds = progress_ms / 1000
    return {
        "time_seconds": f"{seconds:.3f}",
        "mode": mode,
        "font_size": font_size,
        "color": color,
        "send_time": format_timestamp(ctime),
        "send_timestamp": ctime,
        "danmaku_pool": pool,
        "user_hash": mid_hash,
        "row_id": row_id,
        "text": clean_text(text),
    }
