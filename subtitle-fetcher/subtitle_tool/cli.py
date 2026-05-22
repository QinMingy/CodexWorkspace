from __future__ import annotations

import argparse
from pathlib import Path

from .env_check import format_report, run_checks
from .extractor import collect_subtitles
from .writer import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量获取视频或合集字幕，并整理成适合 AI 阅读的资料包。")
    parser.add_argument("url", nargs="?", help="视频、播放列表或合集链接；也可以使用 check 只检查环境。")
    parser.add_argument("--out", default="output", help="输出目录，默认：output")
    parser.add_argument("--langs", default="zh-Hans,zh-CN,zh,zh-TW,en", help="字幕语言优先级，逗号分隔。")
    parser.add_argument("--format", default="markdown,json", help="保留参数；第一版固定输出 Markdown、JSON 和 manifest。")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    output_dir = Path(args.out)

    if args.url == "check":
        report = run_checks(output_dir)
        print(format_report(report))
        return 0 if report.ok else 1

    if not args.url:
        parser.print_help()
        return 2

    report = run_checks(output_dir)
    print(format_report(report))
    if not report.ok:
        return 1

    languages = [lang.strip() for lang in args.langs.split(",") if lang.strip()]
    print("解析链接...")
    try:
        result = collect_subtitles(args.url, output_dir, languages)
    except Exception as exc:
        print(f"处理失败：{exc}")
        return 1

    write_outputs(result)
    ok_count = sum(1 for video in result.videos if video.status == "ok")
    print(f"完成：{output_dir / 'subtitles.md'}")
    print(f"成功 {ok_count} 个，失败 {len(result.videos) - ok_count} 个。")
    return 0
