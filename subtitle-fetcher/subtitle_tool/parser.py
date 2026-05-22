from __future__ import annotations

import html
import re
from pathlib import Path

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
    if suffix == ".srt":
        return parse_srt(text)
    return parse_vtt(text)


def parse_vtt(text: str) -> list[SubtitleSegment]:
    return _parse_blocks(text)


def parse_srt(text: str) -> list[SubtitleSegment]:
    return _parse_blocks(text)


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
