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

工具会检查 Python 版本、`yt-dlp`、`streamlit`、`playwright`、登录浏览器、输出目录写入权限、网络连通性和可选的 `ffmpeg`。

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

需要登录态的视频可以使用工具内置的登录窗口，或者用 Cookies 高级选项：

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
Python 安装完成后，脚本会在同一个窗口里刷新当前 PATH 并继续后续步骤，不需要你手动关闭窗口再重开。
如果环境检查发现依赖缺失，脚本会按 `requirements.txt` 自动补装后再次检查。

安装依赖后启动本地网页客户端：

```powershell
streamlit run app.py
```

客户端支持：

- 输入视频或合集链接。
- 检查本机环境配置。
- 设置输出目录和字幕语言优先级。
- 点击“打开登录窗口”登录视频网站，工具会在本地保存 Cookie，下次自动复用。
- 高级用户也可以填写 `cookies.txt` 路径，或从本机浏览器读取 Cookies。
- 完成后下载 `subtitles.md`、`subtitles.json` 和 `manifest.json`。

Cookies 等同于登录凭证，只建议在自己的电脑上使用，不要把 Cookies 文件分享给别人。

### 推荐登录方式

如果视频需要登录、会员态或地区态：

1. 在客户端里选择要登录的网站，比如 B站或 YouTube。
2. 点击“打开登录窗口”。
3. 在弹出的独立浏览器窗口里正常登录。
4. 登录成功后关闭这个窗口。
5. 回到客户端，直接开始获取字幕。

工具会优先使用你本机已安装的 Chrome 或 Edge 打开一个独立登录窗口，不读取你日常浏览器的 Cookie 数据库。登录状态保存到本项目的 `.auth` 文件夹。下次获取同一网站字幕时，会自动复用；如果过期了，再重新打开登录窗口登录一次即可。

如果电脑没有 Chrome/Edge，才需要安装 Playwright 自带 Chromium：

```powershell
python -m playwright install chromium
```

### cookies.txt 在哪

`cookies.txt` 是高级备用方案。普通使用优先用“打开登录窗口”，不需要自己找这个文件。

如果你确实想手动提供 `cookies.txt`：它不是系统自带文件，需要你从已经登录的视频网站浏览器里导出。

最简单流程：

1. 用浏览器登录视频网站，比如 YouTube 或 B站。
2. 安装一个能导出 `cookies.txt` 的浏览器扩展，搜索关键词：`cookies.txt export`。
3. 打开目标视频网站页面，在扩展里选择导出当前网站 Cookies。
4. 保存成 `cookies.txt`，通常会在“下载”文件夹。
5. 在客户端里填写完整路径，例如：

```text
C:\Users\你的名字\Downloads\cookies.txt
```

如果不知道完整路径：在文件资源管理器里找到 `cookies.txt`，按住 Shift 后右键，选择“复制为路径”。

### Cookies 读取失败

如果看到类似错误：

```text
ERROR: Could not copy Chrome cookie database
```

优先尝试：

- 使用客户端里的“打开登录窗口”，让工具自己保存 Cookie。
- 完全关闭 Chrome 后重试，包括后台进程。
- 改从 Edge 或 Firefox 读取 Cookies。
- 确认工具和浏览器在同一个 Windows 用户下运行。
- 重新运行 `start_client.bat`，它会按 `requirements.txt` 更新 `yt-dlp` 和 Playwright。

如果 Chrome 仍然失败，通常是 Chrome 数据库锁定或系统加密保护导致，建议使用工具内置登录窗口。

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
