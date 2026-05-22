from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import AuthOptions, RunResult, SubtitleChoice, VideoResult, VideoTask
from .organizer import organize_segments
from .parser import parse_subtitle_file

LANGUAGE_PRIORITY = ["zh-Hans", "zh-CN", "zh", "zh-TW", "zh-Hant", "zh-HK", "en"]
ACCESS_PATTERNS = re.compile(
    r"(login|private|premium|member|region|geo|unavailable|forbidden|需要登录|会员|地区|私密)",
    re.IGNORECASE,
)


class ExtractionError(RuntimeError):
    pass


def collect_subtitles(
    source_url: str,
    output_dir: Path,
    languages: list[str] | None = None,
    auth_options: AuthOptions | None = None,
) -> RunResult:
    languages = languages or LANGUAGE_PRIORITY
    auth_options = auth_options or AuthOptions()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    metadata = fetch_metadata(source_url, auth_options)
    tasks = build_tasks(metadata, source_url)
    playlist_title = metadata.get("title") if metadata.get("_type") in {"playlist", "multi_video"} else None
    videos: list[VideoResult] = []
    errors: list[dict[str, Any]] = []

    for task in tasks:
        print(f"[{task.index}/{len(tasks)}] 正在获取字幕：{task.title}")
        try:
            result = process_video(task, raw_dir, languages, auth_options)
        except Exception as exc:
            status = classify_error(str(exc))
            result = base_result(task)
            result.status = status
            result.error = str(exc)
        videos.append(result)

    return RunResult(source_url=source_url, output_dir=output_dir, playlist_title=playlist_title, videos=videos, errors=errors)


def fetch_metadata(url: str, auth_options: AuthOptions | None = None) -> dict[str, Any]:
    command = ytdlp_command() + auth_args(auth_options) + ["--dump-single-json", "--flat-playlist", "--no-warnings", url]
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


def process_video(task: VideoTask, raw_dir: Path, languages: list[str], auth_options: AuthOptions | None = None) -> VideoResult:
    result = base_result(task)
    metadata = fetch_full_video_metadata(task.url, auth_options)
    choice = choose_subtitle(metadata, languages)
    if not choice:
        available = available_subtitle_languages(metadata)
        result.status = "no_subtitles"
        if available:
            result.error = f"找到字幕语言 {', '.join(available)}，但没有可下载的字幕格式。"
        else:
            result.error = "未找到平台字幕。B站很多视频只有弹幕或视频内嵌字幕，没有可下载的 CC 字幕；需要登录的视频请先用“打开登录窗口”登录。"
        return result

    subtitle_path = download_subtitle(task, raw_dir, choice, auth_options)
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


def fetch_full_video_metadata(url: str, auth_options: AuthOptions | None = None) -> dict[str, Any]:
    command = ytdlp_command() + auth_args(auth_options) + ["--dump-single-json", "--no-playlist", "--skip-download", "--no-warnings", url]
    completed = run_command(command, timeout=120)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"metadata_failed: 无法解析视频元信息：{exc}") from exc


def choose_subtitle(metadata: dict[str, Any], languages: list[str]) -> SubtitleChoice | None:
    subtitles = metadata.get("subtitles") or {}
    auto_subtitles = metadata.get("automatic_captions") or {}

    for lang in languages:
        if has_downloadable_entries(subtitles.get(lang)):
            return SubtitleChoice(language=lang, kind="manual", ext=choose_ext(subtitles[lang]))
    for lang in languages:
        if has_downloadable_entries(auto_subtitles.get(lang)):
            return SubtitleChoice(language=lang, kind="auto", ext=choose_ext(auto_subtitles[lang]))

    manual_fallback = first_downloadable_language(subtitles)
    if manual_fallback:
        return SubtitleChoice(language=manual_fallback, kind="manual", ext=choose_ext(subtitles[manual_fallback]))

    auto_fallback = first_downloadable_language(auto_subtitles)
    if auto_fallback:
        return SubtitleChoice(language=auto_fallback, kind="auto", ext=choose_ext(auto_subtitles[auto_fallback]))

    return None


def available_subtitle_languages(metadata: dict[str, Any]) -> list[str]:
    languages: list[str] = []
    for source in (metadata.get("subtitles") or {}, metadata.get("automatic_captions") or {}):
        for language in source:
            if language not in languages:
                languages.append(language)
    return languages


def first_downloadable_language(subtitles: dict[str, list[dict[str, Any]]]) -> str | None:
    for language, entries in subtitles.items():
        if has_downloadable_entries(entries):
            return language
    return None


def has_downloadable_entries(entries: Any) -> bool:
    if not isinstance(entries, list):
        return False
    return any(isinstance(entry, dict) and (entry.get("url") or entry.get("data")) for entry in entries)


def choose_ext(entries: list[dict[str, Any]]) -> str:
    exts = [entry.get("ext") for entry in entries if isinstance(entry, dict)]
    for preferred in ("vtt", "srt", "json", "json3", "srv3", "ttml"):
        if preferred in exts:
            return preferred
    return next((ext for ext in exts if ext), "vtt")


def download_subtitle(task: VideoTask, raw_dir: Path, choice: SubtitleChoice, auth_options: AuthOptions | None = None) -> Path:
    output_template = str(raw_dir / f"{safe_name(task.index, task.title)}.%(ext)s")
    command = ytdlp_command() + auth_args(auth_options) + [
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


def auth_args(auth_options: AuthOptions | None) -> list[str]:
    if not auth_options:
        return []
    args: list[str] = []
    if auth_options.cookie_file:
        args.extend(["--cookies", str(auth_options.cookie_file)])
    if auth_options.cookies_from_browser:
        args.extend(["--cookies-from-browser", auth_options.cookies_from_browser])
    return args


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
