from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from subtitle_tool.auth_store import SITES, cookie_file_path, detect_site
from subtitle_tool.env_check import format_report, run_checks
from subtitle_tool.models import AuthOptions
from subtitle_tool.service import EnvironmentCheckError, run_subtitle_job


DEFAULT_LANGS = "zh-Hans,zh-CN,zh,zh-TW,en"
BROWSERS = ["不使用", "chrome", "edge", "firefox", "brave", "opera", "vivaldi"]


st.set_page_config(page_title="字幕获取工具", page_icon="CC", layout="wide")

st.title("字幕获取工具")
st.caption("输入单个视频或合集链接，获取字幕并整理成适合 AI 阅读的 Markdown + JSON。")

source_url = st.text_input("视频或合集链接", placeholder="粘贴 YouTube、B站视频或合集链接")
detected_site = detect_site(source_url.strip()) if source_url.strip() else None

with st.sidebar:
    st.header("参数")
    output_dir_text = st.text_input("输出目录", value="output")
    langs_text = st.text_input("字幕语言优先级", value=DEFAULT_LANGS)

    st.subheader("登录凭证")
    st.caption("不输入账号密码。公开视频不用登录；需要登录/会员态的视频，点下面按钮登录一次即可。")

    site_keys = list(SITES.keys())
    default_site_index = site_keys.index(detected_site.key) if detected_site else 0
    login_site_key = st.selectbox(
        "要登录的网站",
        site_keys,
        index=default_site_index,
        format_func=lambda key: SITES[key].name,
    )
    saved_cookie_path = cookie_file_path(login_site_key)
    if saved_cookie_path.exists():
        st.success(f"已保存 {SITES[login_site_key].name} 登录状态。")
    else:
        st.info(f"还没有保存 {SITES[login_site_key].name} 登录状态。")

    if st.button("打开登录窗口", use_container_width=True):
        subprocess.Popen([sys.executable, "-m", "subtitle_tool.login_helper", "--site", login_site_key])
        st.info("登录窗口已打开。请在新窗口完成登录，登录成功后关闭该窗口，再回到这里重新点击开始。")

    with st.expander("高级：手动 Cookies"):
        cookie_file_text = st.text_input(
            "cookies.txt 文件完整路径（可选）",
            value="",
            placeholder=r"例如：C:\Users\你的名字\Downloads\cookies.txt",
        )
        browser_choice = st.selectbox("直接从已有浏览器读取 Cookies（可选，不推荐 Chrome）", BROWSERS, index=0)
    if cookie_file_text or browser_choice != "不使用" or saved_cookie_path.exists():
        st.warning("Cookies 等同于登录凭证，请只在自己的电脑上使用，不要分享输出日志中的路径信息。")
    if browser_choice == "chrome":
        st.info("Chrome Cookies 可能被浏览器锁定或系统加密保护。若读取失败，请先完全关闭 Chrome，或改用 cookies.txt / Edge / Firefox。")
    with st.expander("这个登录窗口会做什么？"):
        st.markdown(
            """
            - 工具会打开一个独立的本地浏览器窗口。
            - 你在这个窗口里正常登录视频网站。
            - 登录完成后关闭这个窗口，工具会把 Cookie 保存到本项目的 `.auth` 文件夹。
            - 下次获取同一网站字幕时，会自动复用已保存的登录状态。
            - 如果网站登录过期，再点一次“打开登录窗口”重新登录即可。
            """
        )
    with st.expander("Cookies 读取失败怎么办？"):
        st.markdown(
            """
            - 优先方式：点击“打开登录窗口”，让工具自己保存 Cookie。
            - 如果使用已有浏览器 Cookies，请先完全退出对应浏览器后再运行。
            - Chrome 在 Windows 上更容易因为数据库锁定或加密保护读取失败；可以改试 Edge 或 Firefox。
            - 确认本工具和浏览器是在同一个 Windows 用户下运行。
            - 双击 `start_client.bat` 会自动更新 `yt-dlp` 和 Playwright 浏览器内核。
            """
        )

col_check, col_run = st.columns([1, 1])
output_dir = Path(output_dir_text)
languages = [lang.strip() for lang in langs_text.split(",") if lang.strip()]
auto_cookie_path = cookie_file_path(detected_site.key) if detected_site else None
selected_cookie_path = None
if cookie_file_text.strip():
    selected_cookie_path = Path(cookie_file_text).expanduser()
elif auto_cookie_path and auto_cookie_path.exists():
    selected_cookie_path = auto_cookie_path

auth_options = AuthOptions(
    cookie_file=selected_cookie_path,
    cookies_from_browser=None if browser_choice == "不使用" else browser_choice,
)


def show_report(output_path: Path) -> bool:
    report = run_checks(output_path)
    st.code(format_report(report), language="text")
    if report.ok:
        st.success("环境检查通过。")
    else:
        st.error("环境检查未通过，请按提示修复后重试。")
    return report.ok


def add_download_button(path: Path, label: str, mime: str) -> None:
    if path.exists():
        st.download_button(label, path.read_bytes(), file_name=path.name, mime=mime)


with col_check:
    if st.button("检查环境", use_container_width=True):
        show_report(output_dir)

with col_run:
    start = st.button("开始获取字幕", type="primary", use_container_width=True)

if start:
    if not source_url.strip():
        st.error("请先填写视频或合集链接。")
    elif not languages:
        st.error("请至少填写一个字幕语言代码。")
    else:
        with st.status("正在处理字幕...", expanded=True) as status:
            try:
                st.write("正在检查环境...")
                result = run_subtitle_job(source_url.strip(), output_dir, languages, auth_options)
                ok_count = sum(1 for video in result.videos if video.status == "ok")
                failed_count = len(result.videos) - ok_count
                status.update(label="处理完成", state="complete")
                st.success(f"完成：成功 {ok_count} 个，失败 {failed_count} 个。")
                st.session_state["last_output_dir"] = str(output_dir)
            except EnvironmentCheckError as exc:
                status.update(label="环境检查未通过", state="error")
                st.code(format_report(exc.report), language="text")
            except Exception as exc:
                status.update(label="处理失败", state="error")
                st.error(str(exc))

last_output_dir = Path(st.session_state.get("last_output_dir", output_dir))
if last_output_dir.exists():
    st.divider()
    st.subheader("结果文件")
    st.write(f"输出目录：`{last_output_dir}`")
    col_md, col_json, col_manifest = st.columns(3)
    with col_md:
        add_download_button(last_output_dir / "subtitles.md", "下载 Markdown", "text/markdown")
    with col_json:
        add_download_button(last_output_dir / "subtitles.json", "下载 JSON", "application/json")
    with col_manifest:
        add_download_button(last_output_dir / "manifest.json", "下载运行报告", "application/json")
