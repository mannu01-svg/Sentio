#!/usr/bin/env python3
"""One-time model warmup: pre-download + verify the sentiment models.

Called automatically by start.sh when the HF cache is empty; safe to run
manually (idempotent — cached models are not re-downloaded).

Models:
  - distilbert/distilbert-base-uncased-finetuned-sst-2-english  (256MB)
  - cardiffnlp/twitter-roberta-base-sentiment-latest            (478MB)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spark"))

MODELS = [
    "distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    "cardiffnlp/twitter-roberta-base-sentiment-latest",
]

SAMPLES = {
    MODELS[0]: ("what a great video, loved it", "positive"),
    MODELS[1]: ("this is trash lol", None),  # 3-class: just verify it returns a label
}


def main() -> int:
    from transformers import pipeline

    failed = []
    for model in MODELS:
        print(f"▶ {model} …", flush=True)
        try:
            pipe = pipeline(task="sentiment-analysis", model=model, truncation=True)
            sample, expect = SAMPLES[model]
            result = pipe(sample)[0]
            label = str(result["label"]).lower()
            ok = True if expect is None else label.startswith(expect)
            print(f"  ✓ loaded, sample → {label} ({result['score']:.2f})"
                  + ("" if ok else f"  ⚠ expected {expect}"))
            if not ok:
                failed.append(model)
        except Exception as exc:
            print(f"  ✗ failed: {exc}")
            failed.append(model)

    if failed:
        print(f"\n✗ {len(failed)} model(s) failed: {', '.join(failed)}")
        return 1
    print("\n✓ all sentiment models ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
