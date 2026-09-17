"""Unit tests for spark/nlp.py — run with:  .venv/bin/pytest tests/ -v"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spark"))

from nlp import clean_text, vader_label, vader_analyze  # noqa: E402


class TestCleanText:
    def test_strips_urls(self):
        assert "http" not in clean_text("check https://example.com/x now")

    def test_lowercases(self):
        assert clean_text("GREAT Video!!") == "great video!!"

    def test_collapses_whitespace(self):
        assert clean_text("too   many\n spaces \t here") == "too many spaces here"

    def test_removes_emoji(self):
        assert clean_text("nice work \U0001F44D\U0001F3FC") == "nice work"

    def test_empty(self):
        assert clean_text("") == ""


class TestVaderLabel:
    def test_positive(self):
        assert vader_label(0.6) == "positive"

    def test_negative(self):
        assert vader_label(-0.42) == "negative"

    def test_neutral_band(self):
        assert vader_label(0.03) == "neutral"
        assert vader_label(-0.03) == "neutral"
        assert vader_label(0.0) == "neutral"


class TestVaderAnalyze:
    def test_positive_comment(self):
        out = vader_analyze("absolutely loved this video, best explanation ever")
        assert out["vader_label"] == "positive"
        assert out["vader_score"] > 0.2

    def test_negative_comment(self):
        out = vader_analyze("worst audio quality, terrible and annoying")
        assert out["vader_label"] == "negative"
        assert out["vader_score"] < -0.2

    def test_neutral_comment(self):
        out = vader_analyze("what laptop was used in this demo")
        assert out["vader_label"] in ("neutral", "negative")
        assert -1.0 <= out["vader_score"] <= 1.0

    def test_fields_present(self):
        out = vader_analyze("great content")
        assert set(out) == {"vader_label", "vader_score", "vader_positive", "vader_negative", "vader_neutral"}
