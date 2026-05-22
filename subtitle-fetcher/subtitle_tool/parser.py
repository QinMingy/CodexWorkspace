from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .models import SubtitleSegment

TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}[,.]\d{1,3})"
)
TAG_RE = re.compile(r"<[^>]+>")
STYLE_BLOCK_HEADERS = {"WEBVTT", "STYLE", "REGION", "NOTE"}


def parse_subtitle_file(path: Path) -> list[SubtitleSegment]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json_subtitle(text)
    if suffix == ".srt":
        return parse_srt(text)
    return parse_vtt(text)


def parse_vtt(text: str) -> list[SubtitleSegment]:
    return _parse_blocks(text)


def parse_srt(text: str) -> list[SubtitleSegment]:
    return _parse_blocks(text)


def parse_json_subtitle(text: str) -> list[SubtitleSegment]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    body = data.get("body") if isinstance(data, dict) else None
    if not isinstance(body, list):
        return []

    segments: list[SubtitleSegment] = []
    for item in body:
        segment = parse_json_segment(item)
        if segment:
            segments.append(segment)
    return segments


def parse_json_segment(item: Any) -> SubtitleSegment | None:
    if not isinstance(item, dict):
        return None
    start = item.get("from", item.get("start"))
    end = item.get("to", item.get("end"))
    text = item.get("content") or item.get("text")
    if start is None or end is None or not text:
        return None
    return SubtitleSegment(seconds_to_time(start), seconds_to_time(end), normalize_spaces(clean_text(str(text))))


def _parse_blocks(text: str) -> list[SubtitleSegment]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n{2,}", normalized)
    segments: list[SubtitleSegment] = []
    for block in blocks:
        lines = [line.strip("\ufeff ") for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].split(" ", 1)[0] in STYLE_BLOCK_HEADERS:
            continue
        timestamp_index = next((i for i, line in enumerate(lines) if TIMESTAMP_RE.search(line)), None)
        if timestamp_index is None:
            continue
        match = TIMESTAMP_RE.search(lines[timestamp_index])
        if not match:
            continue
        body = " ".join(clean_text(line) for line in lines[timestamp_index + 1 :])
        body = normalize_spaces(body)
        if body:
            segments.append(SubtitleSegment(normalize_time(match.group("start")), normalize_time(match.group("end")), body))
    return segments


def clean_text(text: str) -> str:
    text = re.sub(r"<c(?:\.[^>]*)?>", "", text)
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("&nbsp;", " ")
    return text


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_time(value: str) -> str:
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        value = f"00:{value}"
    time_part, _, millis = value.partition(".")
    fields = [int(part) for part in time_part.split(":")]
    millis = (millis + "000")[:3] if millis else "000"
    return f"{fields[0]:02d}:{fields[1]:02d}:{fields[2]:02d}.{millis}"


def seconds_to_time(value: Any) -> str:
    seconds = max(float(value), 0.0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole_seconds = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        whole_seconds += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{millis:03d}"
