from __future__ import annotations

from pathlib import Path

import streamlit as st

from subtitle_tool.env_check import format_report, run_checks
from subtitle_tool.models import AuthOptions
from subtitle_tool.service import EnvironmentCheckError, run_subtitle_job


DEFAULT_LANGS = "zh-Hans,zh-CN,zh,zh-TW,en"
BROWSERS = ["不使用", "chrome", "edge", "firefox", "brave", "opera", "vivaldi"]


st.set_page_config(page_title="字幕获取工具", page_icon="CC", layout="wide")

st.title("字幕获取工具")
st.caption("输入单个视频或合集链接，获取字幕并整理成适合 AI 阅读的 Markdown + JSON。")

with st.sidebar:
    st.header("参数")
    output_dir_text = st.text_input("输出目录", value="output")
    langs_text = st.text_input("字幕语言优先级", value=DEFAULT_LANGS)

    st.subheader("登录凭证")
    st.caption("不输入账号密码。需要登录态的视频可使用 cookies.txt，或从本机浏览器读取 Cookies。")
    cookie_file_text = st.text_input("cookies.txt 路径（可选）", value="")
    browser_choice = st.selectbox("从浏览器读取 Cookies（可选）", BROWSERS, index=0)
    if cookie_file_text or browser_choice != "不使用":
        st.warning("Cookies 等同于登录凭证，请只在自己的电脑上使用，不要分享输出日志中的路径信息。")

source_url = st.text_input("视频或合集链接", placeholder="粘贴 YouTube、B站视频或合集链接")

col_check, col_run = st.columns([1, 1])
output_dir = Path(output_dir_text)
languages = [lang.strip() for lang in langs_text.split(",") if lang.strip()]
auth_options = AuthOptions(
    cookie_file=Path(cookie_file_text).expanduser() if cookie_file_text.strip() else None,
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
