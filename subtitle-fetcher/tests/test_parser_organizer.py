import unittest
from pathlib import Path

from subtitle_tool.extractor import auth_args, available_subtitle_languages, choose_subtitle
from subtitle_tool.models import AuthOptions
from subtitle_tool.organizer import organize_segments
from subtitle_tool.parser import parse_json_subtitle, parse_srt, parse_vtt


class ParserOrganizerTests(unittest.TestCase):
    def test_parse_vtt_and_merge_segments(self):
        text = """WEBVTT

    00:00:01.000 --> 00:00:02.000
    Hello

    00:00:02.500 --> 00:00:03.000
    world.
    """
        segments = organize_segments(parse_vtt(text))
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start, "00:00:01.000")
        self.assertEqual(segments[0].end, "00:00:03.000")
        self.assertEqual(segments[0].text, "Hello world.")

    def test_parse_srt_removes_tags(self):
        text = """1
    00:00:01,000 --> 00:00:02,000
    <i>你好</i>

    2
    00:00:04,000 --> 00:00:05,000
    [Music]
    """
        segments = organize_segments(parse_srt(text))
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "你好")

    def test_auth_options_become_ytdlp_args(self):
        args = auth_args(AuthOptions(cookie_file=Path("cookies.txt"), cookies_from_browser="edge"))
        self.assertEqual(args, ["--cookies", "cookies.txt", "--cookies-from-browser", "edge"])

    def test_choose_subtitle_falls_back_to_available_language(self):
        metadata = {
            "subtitles": {
                "ai-zh": [{"ext": "srt", "url": "https://example.test/subtitle.srt"}],
            }
        }
        choice = choose_subtitle(metadata, ["zh-Hans", "zh-CN", "en"])
        self.assertIsNotNone(choice)
        self.assertEqual(choice.language, "ai-zh")
        self.assertEqual(choice.kind, "manual")
        self.assertEqual(choice.ext, "srt")
        self.assertEqual(available_subtitle_languages(metadata), ["ai-zh"])

    def test_parse_bilibili_json_subtitle(self):
        text = """{
            "body": [
                {"from": 1.25, "to": 3.5, "content": "第一句"},
                {"from": 4, "to": 5.75, "content": "<i>第二句</i>"}
            ]
        }"""
        segments = organize_segments(parse_json_subtitle(text))
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].start, "00:00:01.250")
        self.assertEqual(segments[0].end, "00:00:05.750")
        self.assertEqual(segments[0].text, "第一句 第二句")


if __name__ == "__main__":
    unittest.main()
