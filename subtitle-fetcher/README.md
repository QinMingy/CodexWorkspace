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
- 不处理登录、会员、私有视频和地区限制；遇到这些情况会记录原因并继续处理其他视频。
