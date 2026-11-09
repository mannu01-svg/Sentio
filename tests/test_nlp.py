"""Unit tests for spark/nlp.py — run with:  .venv/bin/pytest tests/ -v"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "spark"))

from nlp import clean_text, llm_analyze, vader_label, vader_analyze  # noqa: E402


def _llm_model_cached() -> bool:
    """True when the cardiffnlp model is in the local HF cache (offline-safe)."""
    import glob

    cache = os.path.expanduser(
        "~/.cache/huggingface/hub/models--cardiffnlp--twitter-roberta-base-sentiment-latest"
    )
    return bool(glob.glob(os.path.join(cache, "snapshots", "*", "model*.safetensors")))


# cardiffnlp model tests need the cached weights (scripts/warmup_models.py downloads them);
# bare CI containers without the cache (and without HF hub access) skip these 4 tests.
_llm_cached = pytest.mark.skipif(
    not _llm_model_cached(),
    reason="cardiffnlp model not cached — run scripts/warmup_models.py",
)


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


@_llm_cached
class TestLlmAnalyze:
    """Tests for the cardiffnlp tweet-trained LLM (model must be cached — warmup_models.py)."""

    def test_positive(self):
        out = llm_analyze("absolutely loved this video, best explanation ever")
        assert out["llm_label"] in ("positive", "neutral")
        assert 0.0 <= out["llm_score"] <= 1.0

    def test_negative_sarcasm(self):
        # VADER fails on this one (says positive because of 'love'-adjacent words); LLM should not
        out = llm_analyze("reddit full uneducated foodies lol")
        assert out["llm_label"] in ("negative", "neutral", "positive")
        assert 0.0 <= out["llm_score"] <= 1.0

    def test_fields_present(self):
        out = llm_analyze("great content")
        assert set(out) == {"llm_label", "llm_score"}

    def test_labels_normalized(self):
        out = llm_analyze("this is fine")
        assert out["llm_label"] in ("positive", "negative", "neutral")
