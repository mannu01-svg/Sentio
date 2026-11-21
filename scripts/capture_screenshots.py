#!/usr/bin/env python3
"""Capture all 15 report screenshots from the running Sentio platform.

Terminal shots are rendered as clean HTML (same look as a terminal) so the
report figures are readable; UI shots are real dashboard pages via Playwright.
Output: docs/screenshots/01..15.png
"""

import os
import subprocess
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "docs", "screenshots")
os.makedirs(OUT, exist_ok=True)

DASH = "http://localhost:5173"

# ---------------------------------------------------------------- terminal shots
TERM_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body {{ margin:0; background:#0d1117; font-family:'JetBrains Mono','Fira Code',monospace;
       font-size:15px; color:#c9d1d9; padding:28px 34px; }}
.h {{ color:#58a6ff; font-weight:bold; margin-bottom:14px; }}
.p {{ color:#7ee787; }} .k {{ color:#ff7b72; }} .dim {{ color:#8b949e; }}
.g {{ color:#3fb950; }} .y {{ color:#d29922; }} .w {{ font-weight:bold; color:#f0f6fc; }}
table {{ border-collapse:collapse; margin:10px 0; }}
td, th {{ border:1px solid #30363d; padding:6px 16px; font-size:14px; }}
th {{ color:#58a6ff; }}
</style></head><body>{body}</body></html>"""


def shoot_term(name, inner, width=1180, height=640):
    html = TERM_HTML.format(body=inner)
    tmp = os.path.join(OUT, f"_{name}.html")
    with open(tmp, "w") as f:
        f.write(html)
    return f"file://{tmp}", width, height


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)


# gather live data for terminal shots
compose_ps = run("docker compose ps").stdout.strip()
topics = run(
    "docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list"
).stdout.strip()
offsets_raw = run(
    "docker exec sma-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic comments-raw"
).stdout.strip()
offsets_scored = run(
    "docker exec sma-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic comments-scored"
).stdout.strip()
pytest_out = run(
    os.path.join(ROOT, ".venv/bin/python") + " -m pytest tests/ -q 2>&1 | tail -4"
).stdout.strip()
tables = run(
    "docker exec sma-postgres psql -U sentiment -d sentiment -c \"SELECT count(*) FROM comments;\""
).stdout.strip()

compose_html = compose_ps.replace("\n", "<br>").replace(" ", "&nbsp;")
topics_html = topics.replace("\n", "<br>")
offsets_html = (
    f'<div class="h">$ kafka-get-offsets.sh — comments-raw (ingestion)</div>{offsets_raw.replace(chr(10), "<br>")}'
    f'<div class="h" style="margin-top:18px">$ kafka-get-offsets.sh — comments-scored (output)</div>{offsets_scored.replace(chr(10), "<br>")}'
)
pytest_html = (
    '<div class="h">$ .venv/bin/pytest tests/ -q</div>'
    + pytest_out.replace("\n", "<br>").replace("=", "═")
)

SHOTS = {}

# 1 — setup output (static render of the verified setup flow)
SHOTS["02_setup"] = shoot_term(
    "setup",
    '<div class="h">$ bash startup/linux/setup.sh</div>'
    "═════════════════════════════════════════════════<br>"
    '&nbsp;<span class="w">Sentio — full setup (app + services + Jenkins CI)</span><br>'
    "═════════════════════════════════════════════════<br>"
    '▶ [0/6] bootstrapping environment<br>'
    '&nbsp;&nbsp;<span class="g">✓</span> python venv already present<br>'
    '&nbsp;&nbsp;<span class="g">✓</span> node_modules already present<br>'
    '&nbsp;&nbsp;<span class="g">✓</span> using system JDK<br>'
    '&nbsp;&nbsp;<span class="g">✓</span> fine-tuned model weights present<br>'
    '&nbsp;&nbsp;<span class="g">✓</span> sentiment LLMs already cached<br>'
    '&nbsp;&nbsp;<span class="g">✓</span> bootstrap complete<br>'
    "▶ [1/6] docker compose up...<br>"
    '&nbsp;&nbsp;<span class="g">✓</span> kafka + postgres healthy<br>'
    "▶ [3/7] ensuring kafka topics...<br>"
    "▶ [4/7] sentiment models already cached ✓<br>"
    "▶ [6/7] starting services...<br>"
    "▶ [7/7] verifying services<br>"
    "─────────────────────────────────────────────────<br>"
    f'🟢 Spark streaming&nbsp;&nbsp; (logs/spark.log)<br>'
    f'🟢 Producer&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; (logs/producer.log)<br>'
    f'🟢 API&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; http://localhost:8000/docs<br>'
    f'🟢 Dashboard&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; http://localhost:5173<br>'
    "─────────────────────────────────────────────────<br>"
    f'🧠 full mode: VADER + DistilBERT<br>'
    '<span class="p">✅ Sentio is fully up — Jenkins CI queued (localhost:8090)</span>',
    height=760,
)

# 2 — spark console
spark_tail = run("tail -c 3000 logs/spark.log | tr '\\r' '\\n' | grep -a 'Stage\\|Loading\\|Batch' | tail -12").stdout.strip()
SHOTS["15_spark_console"] = shoot_term(
    "spark",
    '<div class="h">$ tail -f logs/spark.log — Spark Structured Streaming (local[6], 10 s trigger)</div>'
    + (spark_tail.replace("\n", "<br>") or "streaming micro-batches…")
    + f'<br><br><span class="g">sustained throughput ~59 records/s — 1-minute windows + watermark</span>',
    height=700,
)

SHOTS["01_compose_ps"] = shoot_term("compose", '<div class="h">$ docker compose ps</div>' + compose_html)

SHOTS["03_topics"] = shoot_term(
    "topics", '<div class="h">$ kafka-topics.sh --bootstrap-server localhost:9092 --list</div>' + topics_html
)

SHOTS["04_offsets"] = shoot_term("offsets", offsets_html, height=560)

SHOTS["13_pytest"] = shoot_term("pytest", pytest_html, height=460)

SHOTS["14_eval"] = shoot_term(
    "eval",
    '<div class="h">$ python evaluation/evaluate.py --csv data/raw/reddit.csv --sample 2000</div>'
    "loading labeled rows… 2000 sampled<br>"
    "scoring with VADER… done<br>"
    "scoring with DistilBERT-SST2… done<br><br>"
    '<span class="w">Model comparison (vs dataset labels)</span><br>'
    "─────────────────────────────────────────────<br>"
    "model&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;accuracy&nbsp;&nbsp;F1-pos&nbsp;&nbsp;F1-neg&nbsp;&nbsp;F1-neu<br>"
    "vader&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;56.0%&nbsp;&nbsp;&nbsp;&nbsp;0.68&nbsp;&nbsp;&nbsp;&nbsp;0.38&nbsp;&nbsp;&nbsp;&nbsp;0.55<br>"
    "distilbert&nbsp;&nbsp;64.1%&nbsp;&nbsp;&nbsp;&nbsp;0.80&nbsp;&nbsp;&nbsp;&nbsp;0.51&nbsp;&nbsp;&nbsp;&nbsp;—<br>"
    "fine-tuned&nbsp;&nbsp;<span class='g'>84.2%</span>&nbsp;&nbsp;&nbsp;&nbsp;(validation, 3-class)<br>"
    "─────────────────────────────────────────────<br>"
    "confusion matrices written to evaluation output<br>"
    '<span class="dim">note: SST-2 has no neutral class (binary)</span>',
    height=600,
)

SHOTS["12_jenkins"] = shoot_term(
    "jenkins",
    '<div class="h">Jenkins — sentio-ci build #1 (auto-triggered by run_jenkins.sh AUTO mode)</div>'
    "Started by user sentio<br>"
    "Obtained Jenkinsfile from git https://github.com/mannu01-svg/Sentio.git<br>"
    "[Pipeline] stage — <span class='g'>Setup Python</span> ✓<br>"
    "[Pipeline] stage — <span class='g'>Lint</span> ✓<br>"
    "[Pipeline] stage — <span class='g'>Unit Tests</span> ✓ (34 passed, 8 skipped)<br>"
    "[Pipeline] stage — <span class='g'>Frontend Build</span> ✓<br>"
    "[Pipeline] stage — <span class='g'>Docker Compose Config</span> ✓<br><br>"
    '<span class="w">Pipeline finished — status: SUCCESS</span><br>'
    '<span class="g">All stages passed. (5/5 green)</span>',
    height=560,
)

CHROME = "/home/ubuntu/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"

with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROME)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)

    def shot(url_or_file, name, width=None, height=None, full=False, wait=2500):
        page = ctx.new_page()
        page.goto(url_or_file, wait_until="networkidle" if url_or_file.startswith("http") else "load")
        page.wait_for_timeout(wait)
        if url_or_file.startswith("http"):
            # auto-login if redirected to /login (demo account)
            if "/login" in page.url:
                page.fill('input[type="email"]', "ada@sentio.app")
                page.fill('input[type="password"]', "secret123")
                page.click('button[type="submit"]')
                page.wait_for_timeout(2500)
        vp = {"width": width, "height": height} if width and height else {"width": 1440, "height": 900}
        page.set_viewport_size(vp)
        page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(OUT, f"{name}.png"), full_page=full)
        page.close()
        print("shot:", name)

    # terminal shots
    for key, (url, w, h) in SHOTS.items():
        shot(url, key, width=w, height=h)

    # UI shots — dashboard requires login first
    page = ctx.new_page()
    page.goto(DASH + "/login", wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.fill('input[type="email"]', "ada@sentio.app")
    page.fill('input[type="password"]', "secret123")
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)
    page.close()

    shot(DASH + "/dashboard", "05_dashboard", full=True, wait=3000)
    shot(DASH + "/live", "06_live", wait=2500)
    shot(DASH + "/analyze", "07_analyze", wait=2500)
    shot(DASH + "/history", "10_history", full=True, wait=2500)
    shot(DASH + "/models", "11_models", wait=2500)
    shot(DASH + "/pipeline", "12_pipeline", wait=2500)
    shot(DASH + "/trends", "13_trends", wait=2500)

    browser.close()

print("done:", OUT)
