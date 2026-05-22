from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SubtitleSegment:
    start: str
    end: str
    text: str


@dataclass
class VideoTask:
    index: int
    title: str
    url: str
    video_id: str | None = None
    duration: float | None = None
    source: str | None = None
    playlist_title: str | None = None
    playlist_index: int | None = None
    webpage_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubtitleChoice:
    language: str
    kind: str
    ext: str = "vtt"


@dataclass
class AuthOptions:
    cookie_file: Path | None = None
    cookies_from_browser: str | None = None


@dataclass
class VideoResult:
    index: int
    title: str
    url: str
    video_id: str | None
    duration: float | None
    source: str | None
    playlist_title: str | None
    playlist_index: int | None
    subtitle_language: str | None = None
    subtitle_kind: str | None = None
    raw_subtitle_path: Path | None = None
    segments: list[SubtitleSegment] = field(default_factory=list)
    status: str = "pending"
    error: str | None = None


@dataclass
class RunResult:
    source_url: str
    output_dir: Path
    playlist_title: str | None
    videos: list[VideoResult]
    errors: list[dict[str, Any]] = field(default_factory=list)
