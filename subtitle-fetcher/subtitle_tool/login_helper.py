from __future__ import annotations

import argparse
import time

from playwright.sync_api import sync_playwright

from .auth_store import auth_profile_dir, cookie_file_path, get_site, installed_browser_channel, write_netscape_cookie_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="打开登录窗口并保存字幕工具使用的 Cookies。")
    parser.add_argument("--site", required=True, choices=["bilibili", "youtube"], help="要登录的网站。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    site = get_site(args.site)
    profile_dir = auth_profile_dir(site.key)
    cookie_path = cookie_file_path(site.key)

    print(f"正在打开 {site.name} 登录窗口。")
    print("请在弹出的浏览器窗口中完成登录，登录完成后关闭该浏览器窗口。")

    with sync_playwright() as p:
        channel = installed_browser_channel()
        launch_options = {"headless": False}
        if channel:
            launch_options["channel"] = channel
            print(f"将使用本机已安装浏览器：{channel}")
        else:
            print("未检测到本机 Chrome/Edge，将尝试使用 Playwright Chromium。")
        context = p.chromium.launch_persistent_context(str(profile_dir), **launch_options)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(site.login_url, wait_until="domcontentloaded")

        while context.pages:
            time.sleep(1)

        cookies = context.cookies()
        write_netscape_cookie_file(cookies, cookie_path)
        context.close()

    print(f"Cookies 已保存：{cookie_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
