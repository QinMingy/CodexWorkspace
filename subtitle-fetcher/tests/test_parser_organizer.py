import unittest

from subtitle_tool.organizer import organize_segments
from subtitle_tool.parser import parse_srt, parse_vtt


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


if __name__ == "__main__":
    unittest.main()
