from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


MIN_PYTHON = (3, 10)


@dataclass
class CheckItem:
    name: str
    status: str
    message: str
    fix: str | None = None
    required: bool = True


@dataclass
class CheckReport:
    items: list[CheckItem]

    @property
    def ok(self) -> bool:
        return all(item.status != "FAIL" for item in self.items if item.required)


def run_checks(output_dir: Path, network_host: str = "www.youtube.com") -> CheckReport:
    items: list[CheckItem] = []

    if sys.version_info >= MIN_PYTHON:
        items.append(CheckItem("Python 版本", "OK", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"))
    else:
        items.append(
            CheckItem(
                "Python 版本",
                "FAIL",
                f"当前版本 {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}，需要 >= 3.10",
                "请安装 Python 3.10 或更高版本。",
            )
        )

    ytdlp = find_ytdlp()
    if ytdlp:
        version = get_ytdlp_version(ytdlp)
        if version:
            items.append(CheckItem("yt-dlp", "OK", version))
        else:
            items.append(
                CheckItem(
                    "yt-dlp",
                    "FAIL",
                    "已找到 yt-dlp，但无法读取版本。",
                    "请运行：pip install -U yt-dlp",
                )
            )
    else:
        items.append(CheckItem("yt-dlp", "FAIL", "未找到 yt-dlp。", "请运行：pip install -U yt-dlp"))

    items.append(check_output_dir(output_dir))

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        items.append(CheckItem("ffmpeg", "OK", ffmpeg, required=False))
    else:
        items.append(CheckItem("ffmpeg", "WARN", "未检测到；当前字幕获取可继续。", "后续如需音频转写再安装 ffmpeg。", required=False))

    try:
        socket.create_connection((network_host, 443), timeout=3).close()
        items.append(CheckItem("网络连通性", "OK", f"可连接 {network_host}", required=False))
    except OSError as exc:
        items.append(CheckItem("网络连通性", "WARN", f"无法直接连接 {network_host}: {exc}", "如果你使用代理，可忽略此提示。", required=False))

    return CheckReport(items)


def find_ytdlp() -> list[str] | None:
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe]
    try:
        result = subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        return [sys.executable, "-m", "yt_dlp"]
    return None


def get_ytdlp_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command + ["--version"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def check_output_dir(output_dir: Path) -> CheckItem:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".subtitle_tool_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return CheckItem("输出目录", "OK", f"可写：{output_dir}")
    except OSError as exc:
        return CheckItem("输出目录", "FAIL", f"不可写：{output_dir} ({exc})", "请换一个可写目录，或检查目录权限。")


def format_report(report: CheckReport) -> str:
    lines = ["环境检查"]
    for item in report.items:
        lines.append(f"[{item.status}] {item.name}：{item.message}")
        if item.status == "FAIL" and item.fix:
            lines.append("")
            lines.append("修复方式：")
            lines.append(item.fix)
    if not report.ok:
        lines.insert(1, "环境检查未通过")
    return "\n".join(lines)
