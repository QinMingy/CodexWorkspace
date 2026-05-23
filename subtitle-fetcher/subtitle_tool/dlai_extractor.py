from __future__ import annotations

import http.client
import re
import ssl
import time
from html import unescape
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from .models import RunResult, SubtitleSegment, VideoResult

RETRYABLE_ERRORS = (http.client.IncompleteRead, TimeoutError, ConnectionError, ssl.SSLError, OSError)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.texts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "a":
            attrs_dict = dict(attrs)
            self._link_href = attrs_dict.get("href")
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "a" and self._link_href:
            title = clean_text(" ".join(self._link_text))
            if title:
                self.links.append((self._link_href, title))
            self._link_href = None
            self._link_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = clean_text(data)
        if not text:
            return
        self.texts.append(text)
        if self._link_href is not None:
            self._link_text.append(text)


def can_handle(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("learn.deeplearning.ai") and "/courses/" in parsed.path and "/lesson/" in parsed.path


def collect_deeplearning_ai_transcripts(source_url: str, output_dir) -> RunResult:
    source_url = normalize_lesson_url(source_url)
    html = fetch_page(source_url)
    parser = parse_page(html)
    page_cache = {source_url: html}
    lesson_urls = discover_all_lesson_urls(source_url, parser, page_cache)

    course_title = discover_course_title(parser, source_url)
    videos: list[VideoResult] = []
    for index, url in enumerate(lesson_urls, start=1):
        if index > 1:
            time.sleep(1)
        try:
            lesson_html = html if url == source_url else fetch_page(url)
            lesson_parser = parse_page(lesson_html)
            title = discover_lesson_title(lesson_parser, url, index)
            paragraphs = extract_transcript_paragraphs(lesson_parser.texts)
            videos.append(
                VideoResult(
                    index=index,
                    title=title,
                    url=url,
                    video_id=None,
                    duration=None,
                    source="DeepLearning.AI",
                    playlist_title=course_title,
                    playlist_index=index,
                    subtitle_language="en",
                    subtitle_kind="transcript",
                    segments=paragraphs_to_segments(paragraphs),
                    status="ok" if paragraphs else "no_subtitles",
                    error=None if paragraphs else "页面中没有找到 transcript 正文；可能需要登录，或该课节是测验/代码/阅读页。",
                )
            )
        except Exception as exc:
            videos.append(
                VideoResult(
                    index=index,
                    title=f"课节 {index}",
                    url=url,
                    video_id=None,
                    duration=None,
                    source="DeepLearning.AI",
                    playlist_title=course_title,
                    playlist_index=index,
                    status="metadata_failed",
                    error=str(exc),
                )
            )

    return RunResult(source_url=source_url, output_dir=output_dir, playlist_title=course_title, videos=videos)


def discover_all_lesson_urls(source_url: str, parser: PageParser, page_cache: dict[str, str]) -> list[str]:
    lesson_urls = unique_urls([source_url] + discover_lesson_urls(source_url, parser))
    module_entry_urls = list(lesson_urls[:8])

    for module_url in module_entry_urls:
        html = page_cache.get(module_url)
        if html is None:
            time.sleep(0.25)
            html = fetch_page(module_url)
            page_cache[module_url] = html
        for discovered_url in discover_lesson_urls(source_url, parse_page(html)):
            normalized = normalize_lesson_url(discovered_url)
            if normalized not in lesson_urls:
                lesson_urls.append(normalized)

    return lesson_urls[:80]


def fetch_page(url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 subtitle-fetcher",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Connection": "close",
                },
            )
            with urlopen(request, timeout=25) as response:
                return response.read().decode("utf-8", errors="replace")
        except RETRYABLE_ERRORS as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(attempt)
    if last_error:
        raise last_error
    raise RuntimeError("网页读取失败。")


def parse_page(html: str) -> PageParser:
    parser = PageParser()
    parser.feed(html)
    return parser


def discover_lesson_urls(source_url: str, parser: PageParser) -> list[str]:
    source_path = urlparse(source_url).path
    course_match = re.search(r"(/courses/[^/]+/lesson/)", source_path)
    if not course_match:
        return [source_url]

    prefix = course_match.group(1)
    urls: list[str] = []
    for href, title in parser.links:
        absolute = urljoin(source_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc.endswith("learn.deeplearning.ai") and parsed.path.startswith(prefix) and title.strip():
            normalized = normalize_lesson_url(parsed._replace(query="", fragment="").geturl())
            if normalized not in urls:
                urls.append(normalized)
    return urls or [source_url]


def discover_course_title(parser: PageParser, source_url: str) -> str:
    if parser.texts and parser.texts[0].endswith(" - DeepLearning.AI"):
        return parser.texts[0].removesuffix(" - DeepLearning.AI").strip()
    for text in parser.texts:
        if text.endswith(" - DeepLearning.AI"):
            return text.removesuffix(" - DeepLearning.AI").strip()
    path = urlparse(source_url).path
    match = re.search(r"/courses/([^/]+)/", path)
    return match.group(1).replace("-", " ").title() if match else "DeepLearning.AI Course"


def discover_lesson_title(parser: PageParser, url: str, index: int) -> str:
    path_slug = unquote(urlparse(url).path.rstrip("/").split("/")[-1].rstrip("!"))
    path_slug = re.sub(r"[-_]+", " ", path_slug).strip().title()
    if path_slug.lower() == "welcome":
        return "Welcome!"
    return path_slug or f"课节 {index}"


def extract_transcript_paragraphs(texts: list[str]) -> list[str]:
    end = next((i for i, text in enumerate(texts) if text == "course detail"), len(texts))
    start = max(0, end - 80)
    window = texts[start:end]
    paragraphs = [text for text in window if is_transcript_paragraph(text)]
    return dedupe_preserve_order(paragraphs)


def is_transcript_paragraph(text: str) -> bool:
    if len(text) < 60:
        return False
    lowered = text.lower()
    blocked = (
        "sign in",
        "create account",
        "privacy policy",
        "terms of use",
        "course syllabus",
        "membership",
        "session expired",
        "return to cornerstone",
    )
    if any(term in lowered for term in blocked):
        return False
    return bool(re.search(r"[.!?。！？]$", text)) or len(text.split()) >= 12


def paragraphs_to_segments(paragraphs: list[str]) -> list[SubtitleSegment]:
    return [SubtitleSegment("00:00:00.000", "00:00:00.000", paragraph) for paragraph in paragraphs]


def clean_text(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def unique_urls(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_lesson_url(value)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def normalize_lesson_url(url: str) -> str:
    parsed = urlparse(url)
    path = unquote(parsed.path).rstrip("!")
    return parsed._replace(path=path, query="", fragment="").geturl()
