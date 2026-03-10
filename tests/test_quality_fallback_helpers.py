import unittest
from unittest.mock import patch

from scdlbot import quality_fallback as qf


def _aq(
    *,
    lossless: bool,
    bitrate: float,
    sample_rate: int | None,
    max_video_height: int = 0,
    extension: str = "mp3",
    source_url: str = "https://example.test/x",
    title: str = "",
) -> qf.AudioQuality:
    return qf.AudioQuality(
        lossless=lossless,
        bitrate_kbps=bitrate,
        sample_rate=sample_rate,
        extension=extension,
        source_url=source_url,
        title=title,
        max_video_height=max_video_height,
    )


class QualityFallbackPureHelpersTests(unittest.TestCase):
    def test_compute_title_match_ratio(self):
        cases = [
            ("Analog Africa Bahia", "Analog Africa - Bahia (Official Audio)", 1.0),
            ("Daft Punk One More Time", "Daft Punk - One More Time", 1.0),
            ("Daft Punk One More Time", "Daft Punk - Aerodynamic", 0.4),
            ("", "Some title", 0.0),
            ("Some Query", "", 0.0),
        ]
        for query, title, expected in cases:
            with self.subTest(query=query, title=title):
                self.assertAlmostEqual(qf.compute_title_match_ratio(query, title), expected, places=5)

    def test_is_youtube_url_normalization(self):
        cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtu.be/dQw4w9WgXcQ", True),
            ("https://soundcloud.com/artist/track", False),
            ("https://example.com/youtube.com/watch?v=x", False),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(qf._is_youtube_url(url), expected)

    def test_meets_floor_quality(self):
        self.assertTrue(qf._meets_floor(_aq(lossless=True, bitrate=0, sample_rate=96000), min_bitrate_kbps=320, prefer_lossless=True))
        self.assertTrue(qf._meets_floor(_aq(lossless=False, bitrate=320, sample_rate=44100), min_bitrate_kbps=320, prefer_lossless=False))
        self.assertFalse(qf._meets_floor(_aq(lossless=False, bitrate=192, sample_rate=44100), min_bitrate_kbps=320, prefer_lossless=False))
        self.assertFalse(qf._meets_floor(_aq(lossless=False, bitrate=256, sample_rate=48000), min_bitrate_kbps=320, prefer_lossless=True))

    def test_is_candidate_better_tie_breakers(self):
        base = _aq(lossless=False, bitrate=192, sample_rate=44100, max_video_height=720)
        better_lossless = _aq(lossless=True, bitrate=0, sample_rate=44100, max_video_height=0, extension="flac")
        better_bitrate = _aq(lossless=False, bitrate=256, sample_rate=44100, max_video_height=720)
        better_sample_rate = _aq(lossless=False, bitrate=192, sample_rate=48000, max_video_height=720)
        better_height = _aq(lossless=False, bitrate=192, sample_rate=44100, max_video_height=1080)

        self.assertTrue(qf._is_candidate_better(base, None))
        self.assertTrue(qf._is_candidate_better(better_lossless, base))
        self.assertTrue(qf._is_candidate_better(better_bitrate, base))
        self.assertTrue(qf._is_candidate_better(better_sample_rate, base))
        self.assertTrue(qf._is_candidate_better(better_height, base))
        self.assertFalse(qf._is_candidate_better(None, base))
        self.assertFalse(qf._is_candidate_better(base, base))

    def test_search_prefix_candidates_youtube_id_normalization(self):
        class FakeYDLClient:
            def __init__(self, _opts):
                pass

            def extract_info(self, _search_url, download=False):
                self._download = download
                return {
                    "entries": [
                        {"url": "dQw4w9WgXcQ", "extractor_key": "Youtube"},
                        {"webpage_url": "https://soundcloud.com/a/b"},
                        {"url": "not-normalized-id", "extractor_key": "Youtube"},
                    ]
                }

        class FakeYDLModule:
            YoutubeDL = FakeYDLClient

        candidates = qf._search_prefix_candidates("ytsearch10", "rick roll", FakeYDLModule)
        self.assertIn("https://www.youtube.com/watch?v=dQw4w9WgXcQ", candidates)
        self.assertIn("https://soundcloud.com/a/b", candidates)
        self.assertNotIn("not-normalized-id", candidates)


class QualityFallbackFindBetterSourceTests(unittest.TestCase):
    def test_find_better_source_prefers_youtube_hd_on_strong_match(self):
        query = "Analog Africa Bahia"
        current_quality = _aq(lossless=False, bitrate=320, sample_rate=44100, max_video_height=0, source_url="https://old")
        youtube_url = "https://www.youtube.com/watch?v=abcdefghijk"
        flac_url = "https://example.com/analog-africa-bahia"

        def fake_probe(url, _ydl_module, **_kwargs):
            if url == youtube_url:
                return _aq(
                    lossless=False,
                    bitrate=256,
                    sample_rate=48000,
                    max_video_height=1440,
                    extension="m4a",
                    source_url=youtube_url,
                    title="Analog Africa - Bahia",
                )
            if url == flac_url:
                return _aq(
                    lossless=True,
                    bitrate=0,
                    sample_rate=44100,
                    max_video_height=0,
                    extension="flac",
                    source_url=flac_url,
                    title="Analog Africa Bahia",
                )
            return None

        with (
            patch("scdlbot.quality_fallback.discover_youtube_candidates", return_value=[youtube_url]),
            patch("scdlbot.quality_fallback.discover_platform_candidates", return_value=[flac_url]),
            patch("scdlbot.quality_fallback.discover_web_candidates", return_value=[]),
            patch("scdlbot.quality_fallback.probe_remote_quality", side_effect=fake_probe),
        ):
            best = qf.find_better_source(
                query=query,
                current_quality=current_quality,
                ydl_module=object(),
                min_bitrate_kbps=192,
                prefer_lossless=True,
                max_candidates=5,
                web_fallback=False,
                proxy=None,
                source_ip=None,
                prefer_youtube=True,
                youtube_min_height=1080,
                min_title_match=0.45,
            )

        self.assertIsNotNone(best)
        self.assertEqual(best[0], youtube_url)
        self.assertEqual(best[1].max_video_height, 1440)

    def test_find_better_source_returns_none_when_no_candidate_beats_current(self):
        current_quality = _aq(lossless=False, bitrate=320, sample_rate=48000, max_video_height=0, source_url="https://old")
        candidate_url = "https://soundcloud.com/artist/track"

        with (
            patch("scdlbot.quality_fallback.discover_youtube_candidates", return_value=[]),
            patch("scdlbot.quality_fallback.discover_platform_candidates", return_value=[candidate_url]),
            patch("scdlbot.quality_fallback.discover_web_candidates", return_value=[]),
            patch(
                "scdlbot.quality_fallback.probe_remote_quality",
                return_value=_aq(
                    lossless=False,
                    bitrate=192,
                    sample_rate=44100,
                    max_video_height=0,
                    source_url=candidate_url,
                    title="Artist Track",
                ),
            ),
        ):
            best = qf.find_better_source(
                query="Artist Track",
                current_quality=current_quality,
                ydl_module=object(),
                min_bitrate_kbps=320,
                prefer_lossless=False,
                max_candidates=3,
                web_fallback=False,
                proxy=None,
                source_ip=None,
            )

        self.assertIsNone(best)


if __name__ == "__main__":
    unittest.main()
