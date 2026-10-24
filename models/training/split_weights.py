#!/usr/bin/env python3
"""Split/rejoin the fine-tuned model weights for GitHub.

GitHub rejects files >100MB without Git LFS. The fine-tuned DistilBERT weights
are ~268MB, so model.safetensors is split into <=90MB .partNN chunks that push
as normal git blobs; `--join` rebuilds the original file byte-for-byte.

Usage:
    python models/training/split_weights.py --split   # after training
    python models/training/split_weights.py --join    # after cloning
"""

import argparse
import hashlib
import os
import sys

CHUNK = 90 * 1024 * 1024  # 90MB — safely under GitHub's 100MB hard limit


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def split(path: str) -> None:
    if not os.path.exists(path):
        sys.exit(f"{path} not found — train the model first (models/training/finetune.py)")
    checksum = sha256(path)
    with open(path, "rb") as handle:
        index = 0
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            part = f"{path}.part{index:02d}"
            with open(part, "wb") as out:
                out.write(block)
            print(f"wrote {part} ({len(block)/1e6:.1f}MB)")
            index += 1
    with open(f"{path}.sha256", "w") as out:
        out.write(f"{checksum}\n")
    print(f"checksum: {checksum[:16]}…  ({index} parts)")
    print("git add the .partNN files + .sha256; the original stays gitignored")


def join(path: str) -> None:
    checksum_path = f"{path}.sha256"
    if not os.path.exists(checksum_path):
        sys.exit(f"{checksum_path} not found")
    with open(checksum_path) as handle:
        expected = handle.read().strip()
    base = os.path.basename(path)
    directory = os.path.dirname(path) or "."
    parts = sorted(p for p in os.listdir(directory) if p.startswith(base + ".part"))
    if not parts:
        sys.exit("no .partNN chunks found")
    with open(path, "wb") as out:
        for part in parts:
            with open(os.path.join(directory, part), "rb") as handle:
                while True:
                    block = handle.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
            print(f"joined {part}")
    actual = sha256(path)
    if actual != expected:
        sys.exit(f"checksum mismatch! {actual[:16]}… != {expected[:16]}…")
    print(f"OK — {path} rebuilt ({os.path.getsize(path)/1e6:.1f}MB, checksum verified)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--split", action="store_true")
    group.add_argument("--join", action="store_true")
    parser.add_argument("--path", default="models/sentiment-finetuned/model.safetensors")
    args = parser.parse_args()
    if args.split:
        split(args.path)
    else:
        join(args.path)
