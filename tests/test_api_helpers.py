"""Tests for api/main.py helpers (stopwords, normalization)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import STOPWORDS  # noqa: E402


def test_stopwords_loaded():
    assert "the" in STOPWORDS
    assert "and" in STOPWORDS
    assert "video" not in STOPWORDS
