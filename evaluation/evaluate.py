#!/usr/bin/env python3
"""Offline evaluation of sentiment models against dataset ground-truth labels.

Reads the scored comments stored in PostgreSQL (produced by the streaming job)
and reports, for each model:

  - accuracy, precision, recall, F1 (macro) vs the dataset labels
  - confusion matrix
  - VADER vs DistilBERT agreement

Also runs the same metrics on a held-out CSV directly (no streaming needed):
    .venv/bin/python evaluation/evaluate.py --csv data/raw/reddit.csv --sample 5000

Usage:
    .venv/bin/python evaluation/evaluate.py                 # evaluate DB rows
    .venv/bin/python evaluation/evaluate.py --csv FILE      # evaluate a CSV offline
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spark"))

import nlp  # noqa: E402

LABELS = ["positive", "negative", "neutral"]


def normalize_label(raw: str) -> str:
    label = (raw or "").strip().lower()
    if label.startswith("pos"):
        return "positive"
    if label.startswith("neg"):
        return "negative"
    return "neutral"


def confusion(y_true: list[str], y_pred: list[str]) -> dict:
    matrix = {t: {p: 0 for p in LABELS} for t in LABELS}
    for truth, pred in zip(y_true, y_pred):
        matrix[truth][pred] += 1
    return matrix


def precision_recall_f1(matrix: dict) -> dict:
    report = {}
    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[t][label] for t in LABELS if t != label)
        fn = sum(matrix[label][p] for p in LABELS if p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[label] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}
    return report


def accuracy(y_true: list[str], y_pred: list[str]) -> float:
    return round(sum(t == p for t, p in zip(y_true, y_pred)) * 100 / len(y_true), 2) if y_true else 0.0


def evaluate_pairs(y_true: list[str], y_vader: list[str], y_bert: list[str]) -> dict:
    result = {
        "n": len(y_true),
        "vader": {"accuracy": accuracy(y_true, y_vader), "confusion": confusion(y_true, y_vader)},
        "bert": {"accuracy": accuracy(y_true, y_bert), "confusion": confusion(y_true, y_bert)},
        "agreement_pct": accuracy(y_vader, y_bert),
    }
    result["vader"]["per_class"] = precision_recall_f1(result["vader"]["confusion"])
    result["bert"]["per_class"] = precision_recall_f1(result["bert"]["confusion"])
    return result


# ---------- offline CSV mode ----------

def evaluate_csv(path: str, sample: int | None, use_bert: bool = True) -> dict:
    import csv
    import random

    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if sample and len(rows) > sample:
        rows = random.sample(rows, sample)

    text_cols = ["comment", "text", "clean_text", "CONTENT", "content", "body"]
    label_cols = ["label", "sentiment", "category", "CLASS"]

    def pick(row: dict, cols: list[str]) -> str:
        for col in cols:
            if row.get(col) and str(row[col]).strip():
                return str(row[col]).strip()
        return ""

    y_true, y_vader, y_bert = [], [], []
    for row in rows:
        text = nlp.clean_text(pick(row, text_cols))
        truth = normalize_label(pick(row, label_cols))
        if not text:
            continue
        vader = nlp.vader_analyze(text)
        y_true.append(truth)
        y_vader.append(vader["vader_label"])
        if use_bert:
            bert = nlp.bert_analyze(text)
            y_bert.append(bert["bert_label"] if bert["bert_label"] in LABELS else "neutral")

    return evaluate_pairs(y_true, y_vader, y_bert)


# ---------- database mode ----------

def evaluate_db() -> dict:
    import psycopg2
    import psycopg2.extras

    dsn = os.getenv("PG_DSN", "host=localhost port=5432 dbname=sentiment user=sentiment password=sentiment")
    with psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT label, vader_label, bert_label FROM comments
            WHERE label IS NOT NULL AND vader_label IS NOT NULL
            """
        )
        rows = [dict(r) for r in cur.fetchall()]

    y_true = [normalize_label(r["label"]) for r in rows]
    y_vader = [r["vader_label"] for r in rows]
    y_bert = [r["bert_label"] if r["bert_label"] in LABELS else "neutral" for r in rows]
    return evaluate_pairs(y_true, y_vader, y_bert)


def print_report(result: dict) -> None:
    print(json.dumps({
        "samples": result["n"],
        "vader_accuracy_pct": result["vader"]["accuracy"],
        "bert_accuracy_pct": result["bert"]["accuracy"],
        "model_agreement_pct": result["agreement_pct"],
        "vader_per_class": result["vader"]["per_class"],
        "bert_per_class": result["bert"]["per_class"],
    }, indent=2))
    for model in ("vader", "bert"):
        print(f"\n{model.upper()} confusion matrix (rows=true, cols=pred):")
        matrix = result[model]["confusion"]
        header = " " * 12 + "".join(f"{p:>10}" for p in LABELS)
        print(header)
        for truth in LABELS:
            print(f"{truth:>12}" + "".join(f"{matrix[truth][p]:>10}" for p in LABELS))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate sentiment models vs ground truth.")
    parser.add_argument("--csv", help="evaluate a CSV file offline instead of the DB")
    parser.add_argument("--sample", type=int, default=None, help="sample size for CSV mode")
    parser.add_argument("--no-bert", action="store_true", help="skip DistilBERT (VADER only)")
    args = parser.parse_args()

    result = evaluate_csv(args.csv, args.sample, not args.no_bert) if args.csv else evaluate_db()
    print_report(result)


if __name__ == "__main__":
    main()
