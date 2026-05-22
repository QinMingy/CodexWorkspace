# 字幕获取工具

这是一个本地命令行工具，用来从单个视频链接或合集链接中批量获取字幕，并整理成适合 AI 阅读的 Markdown + JSON 资料包。

## 安装

需要 Python 3.10 或更高版本。

```powershell
pip install -r requirements.txt
```

## 检查环境

```powershell
python -m subtitle_tool check
```

工具会检查 Python 版本、`yt-dlp`、输出目录写入权限、网络连通性和可选的 `ffmpeg`。

## 使用

```powershell
python -m subtitle_tool "视频或合集链接"
```

指定输出目录：

```powershell
python -m subtitle_tool "视频或合集链接" --out output
```

指定字幕语言优先级：

```powershell
python -m subtitle_tool "视频或合集链接" --langs zh-Hans,zh-CN,zh,en
```

需要登录态的视频可以使用 Cookies，不需要也不建议输入账号密码：

```powershell
python -m subtitle_tool "视频或合集链接" --cookies "C:\path\to\cookies.txt"
python -m subtitle_tool "视频或合集链接" --cookies-from-browser edge
```

## 可视化客户端

Windows 下可以直接双击：

```text
start_client.bat
```

它会自动检查 Python、创建本地虚拟环境、安装依赖、运行环境检查，并打开可视化客户端。
如果没有检测到 Python，脚本会优先尝试通过 Windows 的 `winget` 自动安装 Python 3.12；如果系统没有 `winget`，会提示你手动安装。
如果环境检查发现依赖缺失，脚本会按 `requirements.txt` 自动补装后再次检查。

安装依赖后启动本地网页客户端：

```powershell
streamlit run app.py
```

客户端支持：

- 输入视频或合集链接。
- 检查本机环境配置。
- 设置输出目录和字幕语言优先级。
- 可选填写 `cookies.txt` 路径，或从本机浏览器读取 Cookies。
- 完成后下载 `subtitles.md`、`subtitles.json` 和 `manifest.json`。

Cookies 等同于登录凭证，只建议在自己的电脑上使用，不要把 Cookies 文件分享给别人。

### Cookies 读取失败

如果看到类似错误：

```text
ERROR: Could not copy Chrome cookie database
```

优先尝试：

- 完全关闭 Chrome 后重试，包括后台进程。
- 改用 `cookies.txt` 文件路径，这是最稳定的方式。
- 改从 Edge 或 Firefox 读取 Cookies。
- 确认工具和浏览器在同一个 Windows 用户下运行。
- 重新运行 `start_client.bat`，它会按 `requirements.txt` 更新 `yt-dlp`。

如果 Chrome 仍然失败，通常是 Chrome 数据库锁定或系统加密保护导致，建议直接使用 `cookies.txt`。

## 输出

默认生成：

```text
output/
  subtitles.md
  subtitles.json
  manifest.json
  raw/
```

- `subtitles.md`：适合直接喂给 AI 的主文件。
- `subtitles.json`：适合后续程序处理的结构化结果。
- `manifest.json`：运行摘要、成功失败数量和失败原因。
- `raw/`：原始字幕文件备份。

## 默认策略

- 第一版优先支持 YouTube 和 B站，依赖 `yt-dlp` 的平台能力。
- 只下载字幕和元信息，不下载视频本体。
- 中文字幕优先，英文兜底。
- 每个视频只保留一个最佳字幕版本。
- 默认不处理登录、会员、私有视频和地区限制；如果提供 Cookies，会把登录态透传给 `yt-dlp` 尝试获取字幕。
