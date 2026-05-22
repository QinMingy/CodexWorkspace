from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import RunResult, SubtitleChoice, VideoResult, VideoTask
from .organizer import organize_segments
from .parser import parse_subtitle_file

LANGUAGE_PRIORITY = ["zh-Hans", "zh-CN", "zh", "zh-TW", "en"]
ACCESS_PATTERNS = re.compile(r"(login|private|premium|member|region|geo|unavailable|forbidden|需要登录|会员|地区|私密)", re.IGNORECASE)


class ExtractionError(RuntimeError):
    pass


def collect_subtitles(source_url: str, output_dir: Path, languages: list[str] | None = None) -> RunResult:
    languages = languages or LANGUAGE_PRIORITY
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    metadata = fetch_metadata(source_url)
    tasks = build_tasks(metadata, source_url)
    playlist_title = metadata.get("title") if metadata.get("_type") in {"playlist", "multi_video"} else None
    videos: list[VideoResult] = []
    errors: list[dict[str, Any]] = []

    for task in tasks:
        print(f"[{task.index}/{len(tasks)}] 正在获取字幕：{task.title}")
        try:
            result = process_video(task, raw_dir, languages)
        except Exception as exc:
            status = classify_error(str(exc))
            result = base_result(task)
            result.status = status
            result.error = str(exc)
        videos.append(result)

    return RunResult(source_url=source_url, output_dir=output_dir, playlist_title=playlist_title, videos=videos, errors=errors)


def fetch_metadata(url: str) -> dict[str, Any]:
    command = ytdlp_command() + ["--dump-single-json", "--flat-playlist", "--no-warnings", url]
    completed = run_command(command, timeout=120)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"metadata_failed: 无法解析 yt-dlp 元信息输出：{exc}") from exc


def build_tasks(metadata: dict[str, Any], source_url: str) -> list[VideoTask]:
    entries = metadata.get("entries")
    if entries:
        tasks: list[VideoTask] = []
        for index, entry in enumerate(entries, start=1):
            if not entry:
                continue
            url = entry.get("url") or entry.get("webpage_url") or source_url
            webpage_url = entry.get("webpage_url") or entry.get("url") or source_url
            tasks.append(
                VideoTask(
                    index=index,
                    title=entry.get("title") or f"视频 {index}",
                    url=webpage_url,
                    video_id=entry.get("id"),
                    duration=entry.get("duration"),
                    source=entry.get("extractor_key") or metadata.get("extractor_key"),
                    playlist_title=metadata.get("title"),
                    playlist_index=entry.get("playlist_index") or index,
                    webpage_url=webpage_url,
                    raw=entry,
                )
            )
        return tasks

    return [
        VideoTask(
            index=1,
            title=metadata.get("title") or "视频 1",
            url=metadata.get("webpage_url") or source_url,
            video_id=metadata.get("id"),
            duration=metadata.get("duration"),
            source=metadata.get("extractor_key"),
            webpage_url=metadata.get("webpage_url") or source_url,
            raw=metadata,
        )
    ]


def process_video(task: VideoTask, raw_dir: Path, languages: list[str]) -> VideoResult:
    result = base_result(task)
    metadata = fetch_full_video_metadata(task.url)
    choice = choose_subtitle(metadata, languages)
    if not choice:
        result.status = "no_subtitles"
        result.error = "未找到中文或英文字幕。"
        return result

    subtitle_path = download_subtitle(task, raw_dir, choice)
    segments = organize_segments(parse_subtitle_file(subtitle_path))
    if not segments:
        result.status = "subtitle_download_failed"
        result.error = "字幕文件已下载，但没有解析出有效文本。"
        result.raw_subtitle_path = subtitle_path
        return result

    result.status = "ok"
    result.subtitle_language = choice.language
    result.subtitle_kind = choice.kind
    result.raw_subtitle_path = subtitle_path
    result.segments = segments
    return result


def fetch_full_video_metadata(url: str) -> dict[str, Any]:
    command = ytdlp_command() + ["--dump-single-json", "--no-playlist", "--skip-download", "--no-warnings", url]
    completed = run_command(command, timeout=120)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"metadata_failed: 无法解析视频元信息：{exc}") from exc


def choose_subtitle(metadata: dict[str, Any], languages: list[str]) -> SubtitleChoice | None:
    subtitles = metadata.get("subtitles") or {}
    auto_subtitles = metadata.get("automatic_captions") or {}

    for lang in languages:
        if lang in subtitles:
            return SubtitleChoice(language=lang, kind="manual", ext=choose_ext(subtitles[lang]))
    for lang in languages:
        if lang in auto_subtitles:
            return SubtitleChoice(language=lang, kind="auto", ext=choose_ext(auto_subtitles[lang]))
    return None


def choose_ext(entries: list[dict[str, Any]]) -> str:
    exts = [entry.get("ext") for entry in entries if isinstance(entry, dict)]
    if "vtt" in exts:
        return "vtt"
    if "srt" in exts:
        return "srt"
    return next((ext for ext in exts if ext), "vtt")


def download_subtitle(task: VideoTask, raw_dir: Path, choice: SubtitleChoice) -> Path:
    output_template = str(raw_dir / f"{safe_name(task.index, task.title)}.%(ext)s")
    command = ytdlp_command() + [
        "--skip-download",
        "--no-playlist",
        "--sub-langs",
        choice.language,
        "--sub-format",
        choice.ext,
        "--output",
        output_template,
    ]
    command.append("--write-auto-subs" if choice.kind == "auto" else "--write-subs")
    command.append(task.url)
    run_command(command, timeout=180)

    candidates = sorted(raw_dir.glob(f"{safe_name(task.index, task.title)}*.{choice.ext}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        candidates = sorted(raw_dir.glob(f"{safe_name(task.index, task.title)}*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise ExtractionError("subtitle_download_failed: yt-dlp 未生成字幕文件。")
    return candidates[0]


def base_result(task: VideoTask) -> VideoResult:
    return VideoResult(
        index=task.index,
        title=task.title,
        url=task.url,
        video_id=task.video_id,
        duration=task.duration,
        source=task.source,
        playlist_title=task.playlist_title,
        playlist_index=task.playlist_index,
    )


def run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError(f"命令超时：{' '.join(command[:2])}") from exc
    except OSError as exc:
        raise ExtractionError(str(exc)) from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "未知错误").strip()
        raise ExtractionError(message)
    return completed


def ytdlp_command() -> list[str]:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    return [sys.executable, "-m", "yt_dlp"]


def classify_error(message: str) -> str:
    if ACCESS_PATTERNS.search(message):
        return "access_restricted"
    if "subtitle" in message.lower() or "字幕" in message:
        return "subtitle_download_failed"
    return "metadata_failed"


def safe_name(index: int, title: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)[:80] or "video"
    return f"{index:03d}-{cleaned}"
