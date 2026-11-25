#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-time environment bootstrap for a completely fresh clone.
# start.sh runs this automatically when .venv / node_modules are missing —
# the user only ever runs ./start.sh.
#
#   - python venv + requirements
#   - frontend node_modules
#   - JDK 17 (user-local, no sudo)
#   - fine-tuned model weights (rejoin from committed chunks)
#   - demo login user
# ---------------------------------------------------------------------------
set -e
# repo root: resolve from this script's location (works from linux/, mac/, or repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$(basename "$SCRIPT_DIR")" in
  # startup/<platform>/ -> repo root is two levels up
  linux|mac|windows) ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")" ;;
  startup)           ROOT="$(dirname "$SCRIPT_DIR")" ;;          # startup/ itself
  *)                 ROOT="$SCRIPT_DIR" ;;                       # repo root
esac
cd "$ROOT"

echo "▶ [0/6] bootstrapping environment (one-time setup)"

# 1. python venv ------------------------------------------------------------
if [ ! -d "$ROOT/.venv" ]; then
  echo "  → creating python venv + installing requirements (~3-5 min)…"
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install --quiet --upgrade pip
  "$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/requirements.txt" || \
    { echo "❌ pip install failed — check requirements.txt"; exit 1; }
  echo "  ✓ python env ready"
else
  echo "  ✓ python venv already present"
fi

# 2. frontend node_modules ---------------------------------------------------
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "  → npm install (frontend)…"
  (cd "$ROOT/frontend" && npm install --silent) || \
    { echo "❌ npm install failed — is node.js installed?"; exit 1; }
  echo "  ✓ frontend deps ready"
else
  echo "  ✓ node_modules already present"
fi

# 3. JDK 17 (user-local, no sudo) --------------------------------------------
#    Skipped entirely when a JDK is already available (JAVA_HOME set, or java
#    17+ on PATH e.g. brew openjdk) — the auto-download below is the fallback.
JDK_DIR="$HOME/.tools/jdk-17"
if [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  echo "  ✓ using existing JDK at $JAVA_HOME"
elif command -v java >/dev/null 2>&1 && java -version 2>&1 | grep -q 'version "17'; then
  echo "  ✓ using system JDK ($(java -version 2>&1 | head -1))"
elif [ ! -d "$JDK_DIR" ]; then
  echo "  → downloading JDK 17 (user-local, ~190MB, one-time)…"
  mkdir -p "$HOME/.tools"
  OS="$(uname -s)"; ARCH="$(uname -m)"
  case "$OS" in
    Darwin)
      if [ "$ARCH" = "arm64" ]; then
        JDK_URL="https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_macos-aarch64_bin.tar.gz"
      else
        JDK_URL="https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_macos-x64_bin.tar.gz"
      fi
      ;;
    *) JDK_URL="https://download.java.net/java/GA/jdk17.0.2/dfd4a8d0985749f896bed50d7138ee7f/8/GPL/openjdk-17.0.2_linux-x64_bin.tar.gz" ;;
  esac
  curl -fsSL -o /tmp/jdk17.tar.gz "$JDK_URL" || { echo "⚠ JDK download failed — Spark needs Java 17: export JAVA_HOME to your JDK"; }
  if [ -f /tmp/jdk17.tar.gz ]; then
    tar xzf /tmp/jdk17.tar.gz -C "$HOME/.tools"
    mv "$HOME/.tools"/jdk-17* "$JDK_DIR" 2>/dev/null || true
    rm -f /tmp/jdk17.tar.gz
    echo "  ✓ JDK 17 ready at $JDK_DIR"
  fi
else
  echo "  ✓ JDK 17 already present"
fi

# 4. fine-tuned model weights (rejoin committed chunks) ----------------------
SAFETENSORS="$ROOT/models/sentiment-finetuned/model.safetensors"
if [ ! -f "$SAFETENSORS" ] && [ -f "$SAFETENSORS.sha256" ]; then
  echo "  → rejoining fine-tuned model weights from committed chunks…"
  "$ROOT/.venv/bin/python" "$ROOT/models/training/split_weights.py" --join \
    || echo "⚠ model rejoin failed — the pipeline still works (cardiffnlp LLM downloads on first run)"
else
  echo "  ✓ fine-tuned model weights present"
fi

# 5. sentiment model warmup (HF cache — downloads cardiffnlp + distilbert) ---
HF_CACHE="$HOME/.cache/huggingface/hub/models--cardiffnlp--twitter-roberta-base-sentiment-latest"
if [ ! -d "$HF_CACHE" ]; then
  echo "  → downloading sentiment LLMs from HuggingFace (one-time, ~5 min)…"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/warmup_models.py" \
    || echo "⚠ model warmup failed — the Spark job will retry on start"
else
  echo "  ✓ sentiment LLMs already cached"
fi

# 6. login users (demo user + seeded admin) -----------------------------------
#    Cross-platform seed scripts (same ones the Windows start.bat uses).
#    Skips gracefully when Postgres isn't up yet — start.sh re-invokes this
#    script after containers are healthy, which completes the seeds.
"$ROOT/.venv/bin/python" "$ROOT/scripts/seed_demo_user.py"
"$ROOT/.venv/bin/python" "$ROOT/scripts/seed_admin.py"

echo "  ✓ bootstrap complete"
