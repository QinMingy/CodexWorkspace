from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .models import RunResult, SubtitleSegment, VideoResult
from .organizer import display_time


def write_outputs(result: RunResult) -> None:
    result.output_dir.mkdir(parents=True, exist_ok=True)
    (result.output_dir / "subtitles.md").write_text(render_markdown(result), encoding="utf-8")
    (result.output_dir / "subtitles.json").write_text(json.dumps(to_json(result), ensure_ascii=False, indent=2), encoding="utf-8")
    (result.output_dir / "manifest.json").write_text(json.dumps(to_manifest(result), ensure_ascii=False, indent=2), encoding="utf-8")


def render_markdown(result: RunResult) -> str:
    lines: list[str] = ["# 字幕整理结果", "", f"- 来源链接：{result.source_url}"]
    if result.playlist_title:
        lines.append(f"- 合集：{result.playlist_title}")
    lines.append(f"- 视频数量：{len(result.videos)}")
    lines.append("")

    if result.playlist_title:
        lines.extend([f"## 合集：{result.playlist_title}", ""])

    for video in result.videos:
        lines.extend([f"### {video.index}. {video.title}", ""])
        lines.append(f"- 来源链接：{video.url}")
        lines.append(f"- 状态：{video.status}")
        if video.subtitle_language:
            lines.append(f"- 字幕语言：{video.subtitle_language}")
        if video.subtitle_kind:
            lines.append(f"- 字幕类型：{video.subtitle_kind}")
        if video.error:
            lines.append(f"- 失败原因：{video.error}")
        lines.append("")
        if video.segments:
            for segment in video.segments:
                lines.extend([f"#### {display_time(segment.start)} - {display_time(segment.end)}", "", segment.text, ""])
        else:
            lines.extend(["无可用字幕内容。", ""])

    errors = collect_errors(result)
    if errors:
        lines.extend(["## 处理报告", ""])
        for error in errors:
            lines.append(f"- [{error['status']}] {error['title']}：{error['error']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_json(result: RunResult) -> dict[str, Any]:
    return {
        "source_url": result.source_url,
        "playlist": {"title": result.playlist_title, "video_count": len(result.videos)},
        "videos": [video_to_json(video) for video in result.videos],
        "errors": result.errors + collect_errors(result),
    }


def to_manifest(result: RunResult) -> dict[str, Any]:
    ok_count = sum(1 for video in result.videos if video.status == "ok")
    errors = result.errors + collect_errors(result)
    return {
        "source_url": result.source_url,
        "output_dir": str(result.output_dir),
        "playlist_title": result.playlist_title,
        "total_videos": len(result.videos),
        "successful_videos": ok_count,
        "failed_videos": len(result.videos) - ok_count,
        "errors": errors,
    }


def video_to_json(video: VideoResult) -> dict[str, Any]:
    data = asdict(video)
    data["raw_subtitle_path"] = str(video.raw_subtitle_path) if video.raw_subtitle_path else None
    data["segments"] = [segment_to_json(segment) for segment in video.segments]
    return data


def segment_to_json(segment: SubtitleSegment) -> dict[str, str]:
    return {"start": segment.start, "end": segment.end, "text": segment.text}


def collect_errors(result: RunResult) -> list[dict[str, Any]]:
    return [
        {"index": video.index, "title": video.title, "url": video.url, "status": video.status, "error": video.error}
        for video in result.videos
        if video.status != "ok"
    ]
