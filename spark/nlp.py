"""NLP scoring functions for the sentiment pipeline.

Three analysis approaches, run side by side on every comment:

1. VADER  (Valence Aware Dictionary and sEntiment Reasoner)
   - classic, rule/lexicon-based, transparent, tuned for social media text
   - returns a compound score in [-1, 1] plus pos/neg/neu proportions

2. DistilBERT fine-tuned on SST-2 (HuggingFace)
   - transformer ("AI") model, context-aware
   - returns a POSITIVE/NEGATIVE label plus confidence

3. RoBERTa fine-tuned on 124M tweets (cardiffnlp, HuggingFace)
   - tweet-trained LLM — understands slang, emojis, sarcasm patterns
   - returns a positive/neutral/negative label plus confidence
   - the authoritative score for social-media comments

All are plain Python functions so they are easy to unit test, and are
invoked inside the Spark job via mapInPandas / UDFs.
"""

from __future__ import annotations

import os

# Models are cached locally (warmup_models.py) — never hit the HF Hub at
# inference time: a hub roundtrip inside a Spark worker costs seconds and
# blocks the whole micro-batch.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

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


BATCH_SIZE = int(__import__("os").getenv("NLP_BATCH_SIZE", "64"))


def _cap_torch_threads() -> None:
    """Spark's JVM overrides OMP_NUM_THREADS=1 inside python workers, so torch
    would run inference single-threaded (~200s per 2k-row batch). NLP_TORCH_THREADS
    (exported in run_spark.sh) survives the JVM env clobber — read it here."""
    try:
        import torch

        torch.set_num_threads(max(1, int(os.getenv("NLP_TORCH_THREADS", "6"))))
    except Exception:
        pass


def warm() -> None:
    """Preload both transformer pipelines + thread caps (once per worker).

    Called at the top of the Spark mapInPandas worker so model loads are paid
    once per forked worker instead of once per batch/row.
    """
    _cap_torch_threads()
    _bert_pipeline()
    _llm_pipeline()


def bert_batch(texts: list[str]) -> list[dict]:
    """DistilBERT over a batch (batched inference is ~4x faster per text)."""
    cleaned = [(t or "")[:512] for t in texts]
    results = _bert_pipeline()(cleaned, batch_size=BATCH_SIZE)
    return [
        {"bert_label": r["label"].lower(), "bert_score": float(r["score"])}
        for r in results
    ]


def bert_analyze(text: str) -> dict:
    """DistilBERT sentiment: label + confidence score."""
    result = _bert_pipeline()(text[:512])[0]
    return {
        "bert_label": result["label"].lower(),   # positive | negative
        "bert_score": float(result["score"]),
    }


LLM_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"

LLM_LABEL_MAP = {"positive": "positive", "neutral": "neutral", "negative": "negative"}


@lru_cache(maxsize=1)
def _llm_pipeline():
    """Lazy-load the tweet-trained RoBERTa (cardiffnlp) once per process."""
    from transformers import pipeline

    return pipeline(
        task="sentiment-analysis",
        model=LLM_MODEL,
        truncation=True,
    )


def llm_analyze(text: str) -> dict:
    """Tweet-trained LLM (cardiffnlp RoBERTa): 3-class label + confidence."""
    result = _llm_pipeline()(text[:512])[0]
    label = str(result["label"]).lower()
    return {
        "llm_label": LLM_LABEL_MAP.get(label, label),  # positive | neutral | negative
        "llm_score": float(result["score"]),
    }


def llm_batch(texts: list[str]) -> list[dict]:
    """LLM over a batch — batched inference is ~4x faster per text than one-by-one."""
    cleaned = [(t or "")[:512] for t in texts]
    results = _llm_pipeline()(cleaned, batch_size=BATCH_SIZE)
    out = []
    for r in results:
        label = str(r["label"]).lower()
        out.append({
            "llm_label": LLM_LABEL_MAP.get(label, label),
            "llm_score": float(r["score"]),
        })
    return out


def analyze_row(row: dict) -> dict:
    """Score one already-cleaned row with all three models (used by Spark mapInPandas)."""
    text = row["cleaned_text"]
    out = dict(row)
    out.update(vader_analyze(text))
    try:
        out.update(bert_analyze(text))
    except Exception:  # model load/oom failures must not kill the stream
        out["bert_label"] = None
        out["bert_score"] = None
    try:
        out.update(llm_analyze(text))
    except Exception:  # LLM failures must not kill the stream either
        out["llm_label"] = None
        out["llm_score"] = None
    return out
