#!/usr/bin/env python3
"""Fine-tune DistilBERT on the Kaggle social-media sentiment data.

Trains on models/training/train.jsonl (70k rows, 3 classes), evaluates on
val.jsonl each epoch, and saves the model + tokenizer to models/sentiment-finetuned
so the pipeline can score with a model trained on OUR data instead of the
generic SST-2 checkpoint.

Usage:
    .venv/bin/python models/training/finetune.py                  # 3 epochs
    .venv/bin/python models/training/finetune.py --epochs 2 --sample 20000
"""

import argparse
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "spark"))

BASE_MODEL = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
LABELS = ["positive", "negative", "neutral"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--sample", type=int, default=None, help="cap train rows (smoke tests)")
    parser.add_argument("--out", default=os.path.join(ROOT, "models", "sentiment-finetuned"))
    args = parser.parse_args()

    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    num_labels = 3
    print(f"loading {BASE_MODEL} with {num_labels} labels …")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=num_labels, ignore_mismatched_sizes=True)

    data_files = {
        "train": os.path.join(ROOT, "models", "training", "train.jsonl"),
        "validation": os.path.join(ROOT, "models", "training", "val.jsonl"),
    }
    ds = load_dataset("json", data_files=data_files)
    if args.sample:
        ds["train"] = ds["train"].shuffle(seed=42).select(range(min(args.sample, len(ds["train"]))))

    label2id = {l: i for i, l in enumerate(LABELS)}
    ds = ds.map(lambda row: {"labels": label2id[row["label"]]}, remove_columns=["label"])

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=128)

    ds = ds.map(tokenize, batched=True, remove_columns=["text"])

    accuracy = __import__("evaluate")
    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = logits.argmax(-1)
        return accuracy.load("accuracy").compute(predictions=preds, references=labels)

    training_args = TrainingArguments(
        output_dir=os.path.join(ROOT, "models", "training", "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        logging_steps=100,
        warmup_steps=200,
        weight_decay=0.01,
        report_to=[],
        use_cpu=not torch.cuda.is_available(),
        dataloader_num_workers=4,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        compute_metrics=compute_metrics,
    )

    ckpt_dir = os.path.join(ROOT, "models", "training", "checkpoints")
    ckpts = sorted(
        (d for d in os.listdir(ckpt_dir) if d.startswith("checkpoint-")),
        key=lambda d: int(d.split("-")[1]),
    ) if os.path.isdir(ckpt_dir) else []
    resume_path = os.path.join(ckpt_dir, ckpts[-1]) if ckpts else None
    train_kwargs = {"resume_from_checkpoint": resume_path} if resume_path else {}
    if resume_path:
        print(f"resuming from {resume_path}")

    print(f"training on {len(ds['train'])} rows for {args.epochs} epochs …")
    trainer.train(**train_kwargs)
    metrics = trainer.evaluate()
    print(f"validation accuracy: {metrics['eval_accuracy']*100:.2f}%")

    os.makedirs(args.out, exist_ok=True)
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    config = {"base_model": BASE_MODEL, "labels": LABELS, "val_accuracy_pct": round(metrics["eval_accuracy"] * 100, 2),
              "train_rows": len(ds["train"]), "epochs": args.epochs}
    with open(os.path.join(args.out, "training_meta.json"), "w") as handle:
        json.dump(config, handle, indent=2)
    print(f"saved fine-tuned model to {args.out}")
    print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
