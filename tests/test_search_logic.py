import unittest
from unittest.mock import patch

from scdlbot import search_logic
from scdlbot.quality_fallback import AudioQuality


class SearchLogicQueryTests(unittest.TestCase):
    def test_build_query_from_message_text_edge_cases(self):
        cases = [
            ("", ""),
            ("   \n\t", ""),
            ("Daft   Punk   One More Time", "Daft Punk One More Time"),
            ("https://example.com/search?q=Daft%20Punk%20One%20More%20Time", "Daft Punk One More Time"),
            ("https://vk.com/audio-2001483468_131483468_8f090be41380f6686b Matt Cooper Brazen Bull", "Matt Cooper Brazen Bull"),
            ("https://site.test/a/b/c", ""),
            ("noise https://site.test/a/b/c?q=xx", ""),
        ]
        for message_text, expected in cases:
            with self.subTest(message_text=message_text):
                self.assertEqual(search_logic.build_query_from_message_text(message_text), expected)

    def test_is_usable_query_low_signal_filtering(self):
        cases = [
            ("Daft Punk One More Time", True),
            ("Кино Группа крови", True),
            ("01-29", False),
            ("audio123456789", False),
            ("deadbeefdeadbeef", False),
            ("music video", False),
            ("A B", False),
        ]
        for query, expected in cases:
            with self.subTest(query=query):
                self.assertEqual(search_logic.is_usable_query(query), expected)

    def test_source_name_and_quality_formatters(self):
        quality = AudioQuality(
            lossless=False,
            bitrate_kbps=320.0,
            sample_rate=48000,
            extension="m4a",
            source_url="https://example.test",
            title="Track",
            max_video_height=1080,
        )
        self.assertEqual(search_logic.get_source_name("www.youtube.com"), "Ютуб")
        self.assertEqual(search_logic.get_source_name("vk.com"), "ВК")
        self.assertEqual(search_logic.get_source_name("m.texamp.com"), "Texamp")
        self.assertEqual(search_logic.get_source_name("www.example.com"), "example")
        self.assertEqual(search_logic.format_quality_label(quality), "320 kbps, 48000 Hz")
        self.assertEqual(
            search_logic.format_search_choice_quality(quality),
            "320 kbps · 48000 Hz · 1080p · M4A",
        )

    def test_scoring_points_prefers_lossless_bitrate_samplerate_videoheight(self):
        lossy = AudioQuality(
            lossless=False,
            bitrate_kbps=320.0,
            sample_rate=44100,
            extension="mp3",
            source_url="u1",
            max_video_height=720,
        )
        lossless = AudioQuality(
            lossless=True,
            bitrate_kbps=0.0,
            sample_rate=96000,
            extension="flac",
            source_url="u2",
            max_video_height=0,
        )
        self.assertGreater(search_logic.get_quality_points(lossless), search_logic.get_quality_points(lossy))


class SearchLogicRankingTests(unittest.TestCase):
    def test_search_high_quality_sources_ranking_and_filters(self):
        query = "Analog Africa Bahia"
        youtube_url = "https://www.youtube.com/watch?v=abcdefghijk"
        sc_url = "https://soundcloud.com/label/track"
        weak_match_url = "https://www.youtube.com/watch?v=zzzzzzzzzzz"
        qualities = {
            youtube_url: AudioQuality(
                lossless=False,
                bitrate_kbps=256.0,
                sample_rate=48000,
                extension="m4a",
                source_url=youtube_url,
                title="Analog Africa - Bahia",
                max_video_height=1440,
            ),
            sc_url: AudioQuality(
                lossless=True,
                bitrate_kbps=0.0,
                sample_rate=44100,
                extension="flac",
                source_url=sc_url,
                title="Analog Africa Bahia",
                max_video_height=0,
            ),
            weak_match_url: AudioQuality(
                lossless=False,
                bitrate_kbps=320.0,
                sample_rate=44100,
                extension="mp3",
                source_url=weak_match_url,
                title="Unrelated documentary soundtrack",
                max_video_height=2160,
            ),
        }

        def fake_probe(url, _ydl_module, **_kwargs):
            return qualities.get(url)

        with (
            patch("scdlbot.search_logic.discover_youtube_candidates", return_value=[youtube_url, weak_match_url]),
            patch("scdlbot.search_logic.discover_platform_candidates", return_value=[sc_url]),
            patch("scdlbot.search_logic.discover_web_candidates", return_value=[]),
            patch("scdlbot.search_logic.probe_remote_quality", side_effect=fake_probe),
        ):
            result = search_logic.search_high_quality_sources(
                query=query,
                ydl_module=object(),
                fallback_max_candidates=5,
                search_result_limit=3,
                enable_web_fallback=False,
                youtube_min_height=1080,
                min_title_match=0.45,
            )

        self.assertEqual([url for url, _ in result], [youtube_url, sc_url])
        self.assertEqual(len(result), 2)

    def test_search_high_quality_sources_deduplicates_candidates(self):
        target_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        quality = AudioQuality(
            lossless=False,
            bitrate_kbps=192.0,
            sample_rate=44100,
            extension="m4a",
            source_url=target_url,
            title="Rick Astley - Never Gonna Give You Up",
            max_video_height=1080,
        )
        call_counter = {"count": 0}

        def fake_probe(url, _ydl_module, **_kwargs):
            call_counter["count"] += 1
            return quality if url == target_url else None

        with (
            patch("scdlbot.search_logic.discover_youtube_candidates", return_value=[target_url]),
            patch("scdlbot.search_logic.discover_platform_candidates", return_value=[target_url, target_url]),
            patch("scdlbot.search_logic.discover_web_candidates", return_value=[target_url]),
            patch("scdlbot.search_logic.probe_remote_quality", side_effect=fake_probe),
        ):
            result = search_logic.search_high_quality_sources(
                query="Rick Astley Never Gonna Give You Up",
                ydl_module=object(),
                fallback_max_candidates=5,
                search_result_limit=5,
                enable_web_fallback=True,
                youtube_min_height=720,
                min_title_match=0.3,
            )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], target_url)
        self.assertEqual(call_counter["count"], 1)


if __name__ == "__main__":
    unittest.main()
