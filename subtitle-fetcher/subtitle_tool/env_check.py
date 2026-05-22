from __future__ import annotations

import importlib.util
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .auth_store import installed_browser_channel


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

    items.append(check_python_package("yt-dlp", "yt_dlp", "pip install -U yt-dlp"))
    items.append(check_python_package("streamlit", "streamlit", "pip install -U streamlit"))
    items.append(check_python_package("playwright", "playwright", "pip install -U playwright"))
    items.append(check_python_package("curl_cffi", "curl_cffi", "pip install -r requirements.txt", required=False))
    items.append(check_youtube_js_runtime())
    items.append(check_login_browser())
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


def check_python_package(name: str, module_name: str, fix: str, required: bool = True) -> CheckItem:
    if importlib.util.find_spec(module_name):
        version = get_module_version(module_name)
        return CheckItem(name, "OK", version or "已安装", required=required)
    status = "FAIL" if required else "WARN"
    return CheckItem(name, status, "未安装。", f"请运行：{fix}", required=required)


def check_youtube_js_runtime() -> CheckItem:
    for runtime in ("deno", "node"):
        path = shutil.which(runtime)
        if path:
            version = runtime_version(runtime)
            return CheckItem("YouTube JS runtime", "OK", f"{runtime}: {version or path}", required=False)
    return CheckItem(
        "YouTube JS runtime",
        "WARN",
        "未检测到 Deno 或 Node。YouTube 字幕获取可能失败或触发 429。",
        "建议安装 Deno：winget install DenoLand.Deno",
        required=False,
    )


def get_module_version(module_name: str) -> str | None:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", module_name.replace("_", "-")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return None


def runtime_version(command: str) -> str | None:
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()[0].strip() if result.stdout else None


def check_login_browser() -> CheckItem:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return CheckItem("登录浏览器", "FAIL", "Playwright 未安装。", "请运行：pip install -r requirements.txt")

    channel = installed_browser_channel()
    try:
        with sync_playwright() as playwright:
            if channel:
                browser = playwright.chromium.launch(channel=channel, headless=True)
                browser.close()
                return CheckItem("登录浏览器", "OK", f"可使用本机浏览器：{channel}。")
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        return CheckItem("登录浏览器", "OK", "可使用 Playwright Chromium。")
    except Exception as exc:
        return CheckItem(
            "登录浏览器",
            "WARN",
            f"未检测到可直接使用的登录浏览器：{exc}",
            "建议安装 Chrome 或 Edge；如果仍需内置浏览器，再运行：python -m playwright install chromium",
            required=False,
        )


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
    if not report.ok:
        lines.append("环境检查未通过")
    for item in report.items:
        lines.append(f"[{item.status}] {item.name}：{item.message}")
        if item.status == "FAIL" and item.fix:
            lines.append("")
            lines.append("修复方式：")
            lines.append(item.fix)
    return "\n".join(lines)
