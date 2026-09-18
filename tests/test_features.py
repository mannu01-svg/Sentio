"""Tests for fetcher URL parsing + spam heuristic + new API endpoints."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fetcher"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))

from fetcher.fetchers import detect_platform, parse_pasted, REDDIT_URL, YT_URL  # noqa: E402
from api.main import spam_score  # noqa: E402


class TestPlatformDetection:
    def test_youtube_watch(self):
        assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"

    def test_youtube_short(self):
        assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"

    def test_youtube_shorts(self):
        assert detect_platform("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "youtube"

    def test_reddit(self):
        assert detect_platform("https://www.reddit.com/r/programming/comments/1ao4zyz/title_here/") == "reddit"

    def test_unknown(self):
        assert detect_platform("https://example.com/foo") == "unknown"

    def test_youtube_id_extraction(self):
        assert YT_URL.search("https://youtu.be/dQw4w9WgXcQ?t=30").group(1) == "dQw4w9WgXcQ"

    def test_reddit_id_extraction(self):
        m = REDDIT_URL.search("https://old.reddit.com/r/FIREUK/comments/1ao4zyz/side_hustles/")
        assert m.group(2) == "1ao4zyz"


class TestPasteParser:
    def test_parses_lines(self):
        result = parse_pasted("great video\n\nloved it\nbad quality")
        assert len(result["comments"]) == 3
        assert result["comments"][0]["text"] == "great video"
        assert result["source"] == "paste"
        assert all(c["post_id"] == result["post_id"] for c in result["comments"])

    def test_empty(self):
        assert parse_pasted("  \n  ")["comments"] == []


class TestSpamHeuristic:
    def test_clean_comment(self):
        out = spam_score("this video really helped me understand recursion")
        assert not out["is_spam"]

    def test_promo_spam(self):
        out = spam_score("SUBSCRIBE to my channel http://x.com http://y.com FREE CRYPTO giveaway")
        assert out["is_spam"]
        assert "promo phrases" in out["spam_reasons"] or "multiple links" in out["spam_reasons"]

    def test_repeated_chars(self):
        out = spam_score("niceeeeeeeeeee")
        assert out["spam_score"] > 0
