"""NLP scoring functions for the sentiment pipeline.

Two analysis approaches, run side by side on every comment:

1. VADER  (Valence Aware Dictionary and sEntiment Reasoner)
   - classic, rule/lexicon-based, transparent, tuned for social media text
   - returns a compound score in [-1, 1] plus pos/neg/neu proportions

2. DistilBERT fine-tuned on SST-2 (HuggingFace)
   - transformer ("AI") model, context-aware
   - returns a POSITIVE/NEGATIVE label plus confidence

Both are plain Python functions so they are easy to unit test, and are
invoked inside the Spark job via mapInPandas / UDFs.
"""

from __future__ import annotations

from functools import lru_cache

import re

VADER_NEUTRAL_BAND = 0.05  # |compound| <= band -> Neutral (VADER's default advice)


def clean_text(text: str) -> str:
    """Normalize raw comment text: URLs, emojis/html, whitespace, case."""
    text = re.sub(r"http[s]?://\S+|www\.\S+", " ", text)   # urls
    text = re.sub(r"&#\d+;?|&\w+;", " ", text)             # html entities
    text = re.sub(r"[\U00010000-\U0010FFFF]", " ", text)   # non-bmp emoji
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def vader_scores(text: str) -> dict:
    """Full VADER output: compound, positive, negative, neutral proportions."""
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return _vader_analyzer().polarity_scores(text)


def vader_label(compound: float) -> str:
    """Map a VADER compound score to a Positive/Negative/Neutral label."""
    if compound >= VADER_NEUTRAL_BAND:
        return "positive"
    if compound <= -VADER_NEUTRAL_BAND:
        return "negative"
    return "neutral"


def vader_analyze(text: str) -> dict:
    """Convenience: VADER scores + derived label in one call."""
    scores = vader_scores(text)
    return {
        "vader_score": scores["compound"],
        "vader_positive": scores["pos"],
        "vader_negative": scores["neg"],
        "vader_neutral": scores["neu"],
        "vader_label": vader_label(scores["compound"]),
    }


@lru_cache(maxsize=1)
def _vader_analyzer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return SentimentIntensityAnalyzer()


@lru_cache(maxsize=1)
def _bert_pipeline():
    """Lazy-load the DistilBERT SST-2 pipeline once per process."""
    from transformers import pipeline

    return pipeline(
        task="sentiment-analysis",
        model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
        truncation=True,
    )


def bert_analyze(text: str) -> dict:
    """DistilBERT sentiment: label + confidence score."""
    result = _bert_pipeline()(text[:512])[0]
    return {
        "bert_label": result["label"].lower(),   # positive | negative
        "bert_score": float(result["score"]),
    }


def analyze_row(row: dict) -> dict:
    """Score one already-cleaned row with both models (used by Spark mapInPandas)."""
    text = row["cleaned_text"]
    out = dict(row)
    out.update(vader_analyze(text))
    try:
        out.update(bert_analyze(text))
    except Exception:  # model load/oom failures must not kill the stream
        out["bert_label"] = None
        out["bert_score"] = None
    return out
