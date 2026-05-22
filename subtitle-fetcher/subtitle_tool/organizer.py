from __future__ import annotations

import re

from .models import SubtitleSegment

NOISE_RE = re.compile(r"^\s*(\[?(music|applause|laughter|silence|音楽|音乐|掌声|笑声)\]?|♪+)\s*$", re.IGNORECASE)


def organize_segments(segments: list[SubtitleSegment], max_chars: int = 500, max_gap_seconds: float = 2.5) -> list[SubtitleSegment]:
    cleaned = dedupe_segments(remove_noise(segments))
    if not cleaned:
        return []

    paragraphs: list[SubtitleSegment] = []
    current = cleaned[0]
    for segment in cleaned[1:]:
        combined_text = f"{current.text} {segment.text}".strip()
        gap = time_to_seconds(segment.start) - time_to_seconds(current.end)
        should_merge = gap <= max_gap_seconds and len(combined_text) <= max_chars and not ends_sentence(current.text)
        if should_merge:
            current = SubtitleSegment(current.start, segment.end, combined_text)
        else:
            paragraphs.append(current)
            current = segment
    paragraphs.append(current)
    return paragraphs


def remove_noise(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    return [segment for segment in segments if segment.text and not NOISE_RE.match(segment.text)]


def dedupe_segments(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    deduped: list[SubtitleSegment] = []
    last_text = ""
    for segment in segments:
        text = segment.text.strip()
        if text == last_text:
            continue
        deduped.append(SubtitleSegment(segment.start, segment.end, text))
        last_text = text
    return deduped


def ends_sentence(text: str) -> bool:
    return text.rstrip().endswith((".", "?", "!", "。", "？", "！"))


def time_to_seconds(value: str) -> float:
    time_part, _, millis = value.partition(".")
    hours, minutes, seconds = [int(part) for part in time_part.split(":")]
    return hours * 3600 + minutes * 60 + seconds + (int((millis + "000")[:3]) / 1000 if millis else 0)


def display_time(value: str) -> str:
    return value.split(".", 1)[0]
