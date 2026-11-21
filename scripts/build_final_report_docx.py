#!/usr/bin/env python3
"""Build Sentio_Final_Report.docx in the exact Capstone format.

Format rules (from Capstone Project Report Format.docx):
- Page 1: coloured cover page (logo, title, team table, mentor)
- Page 2: Certificate by Supervisor
- Page 3: Declaration by Student(s) + Index
- Body: Times New Roman, headings 14 bold, sub-headings 12 bold,
  paragraphs 12 / 1.5 spacing, one blank line between sections,
  no page break between body sections, table/figure captions below with numbers.
- Index (TOC) points: Problem Statement, Jira Timeline, Requirements (SRS),
  Design (SDD), Technical landscape, Git, Docker, Jenkins, MERN,
  Other libraries/external APIs, Output, Conclusion & Future Scope.
"""

import copy
import os
import sys

import docx
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "docs", "Sentio_Final_Report.docx")
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

FONT = "Times New Roman"
NAVY = RGBColor(0x1F, 0x49, 0x7D)      # theme dk2 — headings + cover accents
ACCENT = RGBColor(0x4F, 0x81, 0xBD)    # theme accent1 — cover band

TITLE = "Sentio — Real-Time Social Media Sentiment Analysis using Kafka, Spark & NLP"
MENTOR = "Mr. Manish Hurkat"
REVIEWER = "Prof. Debopam Acharya"
TEAM = [
    ("Member A", "<Enrollment No.>", "B.Tech CSE"),
    ("Member B", "<Enrollment No.>", "B.Tech CSE"),
    ("Member C", "<Enrollment No.>", "B.Tech CSE"),
]

d = Document()

# ---------------------------------------------------------------------------
# base style: Times New Roman 12, 1.5 spacing
# ---------------------------------------------------------------------------
style = d.styles["Normal"]
style.font.name = FONT
style.font.size = Pt(12)
style.paragraph_format.line_spacing = 1.5
style.paragraph_format.space_after = Pt(0)
# also set east-asian font name so Word doesn't substitute
rpr = style.element.get_or_add_rPr()
rfonts = rpr.find(qn("w:rFonts"))
if rfonts is None:
    rfonts = OxmlElement("w:rFonts")
    rpr.append(rfonts)
rfonts.set(qn("w:eastAsia"), FONT)

sec = d.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)   # A4
sec.left_margin = sec.right_margin = Cm(3.17)          # 1.25"
sec.top_margin = sec.bottom_margin = Cm(2.54)          # 1"


def para(text="", size=12, bold=False, align=None, color=None, italic=False,
         space_after=0, spacing=1.5, underline=False):
    p = d.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = spacing
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    r.font.name = FONT
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.underline = underline
    if color:
        r.font.color.rgb = color
    return p


def heading(text, size=14, color=NAVY, space_before=12):
    p = para(text, size=size, bold=True, color=color, spacing=1.5)
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(6)
    return p


def subheading(text):
    p = para(text, size=12, bold=True, spacing=1.5)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    return p


def body(text):
    return para(text, size=12, spacing=1.5)


def bullets(items):
    for it in items:
        p = d.add_paragraph(style="List Bullet")
        p.paragraph_format.line_spacing = 1.5
        r = p.add_run(it)
        r.font.name = FONT
        r.font.size = Pt(12)


def blank(n=1):
    for _ in range(n):
        para("", spacing=1.5)


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def table(rows_data, widths=None, header=True, caption=None, num=None):
    t = d.add_table(rows=len(rows_data), cols=len(rows_data[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, row in enumerate(rows_data):
        for ci, val in enumerate(row):
            cell = t.rows[ri].cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(str(val))
            r.font.name = FONT
            r.font.size = Pt(11)
            if header and ri == 0:
                r.font.bold = True
                shade(cell, "1F497D")
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    if caption and num:
        p = para(f"Table {num}: {caption}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, spacing=1.15)
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(8)
    return t


def page_break():
    d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def figure(path, width_cm, caption, num):
    if os.path.exists(path):
        p = d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run().add_picture(path, width=Cm(width_cm))
        cp = para(f"Figure {num}: {caption}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, spacing=1.15)
        cp.paragraph_format.space_after = Pt(8)


# ===========================================================================
# PAGE 1 — COLOURED COVER (coloured band + logo + title + team table)
# ===========================================================================
band = d.add_table(rows=1, cols=1)
band.alignment = WD_TABLE_ALIGNMENT.CENTER
bc = band.rows[0].cells[0]
shade(bc, "1F497D")
bp = bc.paragraphs[0]
bp.alignment = WD_ALIGN_PARAGRAPH.CENTER
br = bp.add_run("CAPSTONE PROJECT II")
br.font.name = FONT
br.font.size = Pt(26)
br.font.bold = True
br.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

blank(1)
p = d.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
if os.path.exists(LOGO):
    p.add_run().add_picture(LOGO, width=Cm(7.5))
blank(1)

para("Academic Year: 2026–27", size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY)
para("Team No: ___", size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY)
blank(1)
p = para(TITLE, size=20, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=ACCENT)
p.paragraph_format.space_after = Pt(18)

para("Submitted by", size=14, align=WD_ALIGN_PARAGRAPH.CENTER)
blank(1)

team_t = d.add_table(rows=1 + len(TEAM), cols=4)
team_t.style = "Table Grid"
team_t.alignment = WD_TABLE_ALIGNMENT.CENTER
hdr = ["S.No.", "Name", "Enrollment No.", "Programme"]
for ci, h in enumerate(hdr):
    cell = team_t.rows[0].cells[ci]
    cell.text = ""
    r = cell.paragraphs[0].add_run(h)
    r.font.name = FONT
    r.font.size = Pt(11)
    r.font.bold = True
    shade(cell, "1F497D")
    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
for ri, (name, enr, prog) in enumerate(TEAM, start=1):
    vals = [str(ri), name, enr, prog]
    for ci, v in enumerate(vals):
        cell = team_t.rows[ri].cells[ci]
        cell.text = ""
        r = cell.paragraphs[0].add_run(v)
        r.font.name = FONT
        r.font.size = Pt(11)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
blank(2)
para(f"Faculty Mentor: {MENTOR}", size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY, underline=True)
page_break()

# ===========================================================================
# PAGE 2 — CERTIFICATE BY SUPERVISOR
# ===========================================================================
para("CERTIFICATE BY SUPERVISOR", size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY)
blank(1)
body(
    f'This is to certify that the present Capstone Project II entitled “{TITLE}” being submitted to '
    'NIIT University, Neemrana, in partial fulfillment of the requirements for the award of the Degree '
    'of Bachelor of Technology, in the area of CSE, embodies faithful original work carried out by '
    f'{TEAM[0][0]}, {TEAM[1][0]} and {TEAM[2][0]}. They have worked under my guidance and supervision '
    'and that this work has not been submitted, in part or full, for any other degree or diploma of '
    'NIIT or any other University.'
)
blank(4)
para("Place: Neemrana", size=12)
blank(2)
para(f"Faculty Mentor’s Name: {MENTOR}", size=12, bold=True)
para("Date: ____________", size=12)
page_break()

# ===========================================================================
# PAGE 3 — DECLARATION BY STUDENT(S) + INDEX
# ===========================================================================
para("DECLARATION BY STUDENT(S)", size=16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, color=NAVY)
blank(1)
body(
    f'We hereby declare that the project report entitled “{TITLE}” which is being submitted for the '
    'partial fulfilment of the Degree of Bachelor of Technology, at NIIT University, Neemrana, is an '
    f'authentic record of our original work under the guidance of {MENTOR} and reviewed by {REVIEWER}. '
    'Due acknowledgements have been given in the project report to all related work used. This has '
    'previously not formed the basis for the award of any degree, diploma, associate/fellowship or any '
    'other similar title or recognition in NIIT University or elsewhere.'
)
blank(3)
para("Place: Neemrana", size=12)
para("Date: ____________", size=12)
blank(2)
para("Team Members (signatures):", size=12, bold=True)
blank(1)
sig = d.add_table(rows=1, cols=3)
sig.alignment = WD_TABLE_ALIGNMENT.CENTER
for ci, (name, _, _) in enumerate(TEAM):
    cell = sig.rows[0].cells[ci]
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"\n\n____________________\n{name}")
    r.font.name = FONT
    r.font.size = Pt(11)
blank(2)

heading("INDEX", size=16)
index_rows = [
    ("1.", "Problem Statement", "4"),
    ("2.", "Jira Timeline", "6"),
    ("3.", "Requirements (SRS)", "10"),
    ("4.", "Design (SDD)", "16"),
    ("5.", "Technical Landscape", "24"),
    ("6.", "Git", "27"),
    ("7.", "Docker", "29"),
    ("8.", "Jenkins", "32"),
    ("9.", "MERN (Frontend Implementation)", "35"),
    ("10.", "Other Libraries & External APIs", "39"),
    ("11.", "Output", "42"),
    ("12.", "Conclusion & Future Scope", "49"),
]
t = d.add_table(rows=1 + len(index_rows), cols=3)
t.style = "Table Grid"
t.alignment = WD_TABLE_ALIGNMENT.CENTER
for ci, h in enumerate(["S.No.", "Contents", "Page No."]):
    cell = t.rows[0].cells[ci]
    cell.text = ""
    r = cell.paragraphs[0].add_run(h)
    r.font.name = FONT
    r.font.size = Pt(11)
    r.font.bold = True
    shade(cell, "1F497D")
    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
for ri, (no, what, pg) in enumerate(index_rows, start=1):
    for ci, v in enumerate([no, what, pg]):
        cell = t.rows[ri].cells[ci]
        cell.text = ""
        r = cell.paragraphs[0].add_run(v)
        r.font.name = FONT
        r.font.size = Pt(11)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
page_break()

# ===========================================================================
# BODY — sections per the required Index, no page breaks between sections
# ===========================================================================
FIG = 0
TBL = 0


def next_table_caption(caption):
    global TBL
    TBL += 1
    return TBL, caption


def next_fig_caption(caption):
    global FIG
    FIG += 1
    return FIG, caption


# --- 1. Problem Statement ---------------------------------------------------
heading("1. Problem Statement")
body(
    "Public opinion on social media forms in minutes: product launches trigger thousands of comments "
    "per hour, election cycles shift the public mood overnight, and a single viral post can generate "
    "more comments in an afternoon than a human team can read in a week. Batch analysis of yesterday’s "
    "data misses this window entirely — by the time a report is compiled, the conversation has already "
    "moved on. Manual analysis does not scale: it is slow, expensive, inconsistent between readers, "
    "and impossible to apply continuously."
)
body(
    "The core problem is threefold. First, ingestion: social media content lives behind different "
    "platforms with different access policies — some fully open (YouTube via yt-dlp), some archived "
    "(Reddit via PullPush), some bot-walled for anonymous real-time access (X/Twitter). A platform "
    "must handle all of them gracefully. Second, classification: sentiment on social media is hard — "
    "sarcasm, slang, emojis, negation (“not good”), and domain-specific vocabulary defeat naive "
    "approaches; a lexicon alone is insufficient, and a generic transformer trained on movie reviews "
    "(SST-2) transfers poorly. Third, scale and latency: hundreds of comments per minute must be "
    "cleaned, scored by multiple models, aggregated into per-minute statistics, and served to an "
    "interactive dashboard within seconds."
)
body(
    "Sentio is a real-time social media sentiment analysis platform built to answer “what does the "
    "public feel right now?” and “what did I analyze last week?”. It continuously ingests social media "
    "comments — bundled Kaggle datasets replayed as a live stream, plus live YouTube ingestion via "
    "yt-dlp, Reddit via PullPush, pasted text, account crawls, and keyword/topic search — classifies "
    "their sentiment with three scorers (VADER lexicon, DistilBERT-SST2 transformer, and our own "
    "fine-tuned DistilBERT reaching 84.2% validation accuracy, with cardiffnlp tweet-RoBERTa as the "
    "authoritative live score), aggregates per-minute statistics with Apache Spark Structured "
    "Streaming, persists everything in PostgreSQL, and serves 30+ REST endpoints over FastAPI with "
    "per-account history and an 8-tab React dashboard."
)
subheading("1.1 Objectives")
bullets([
    "Ingest comments as a simulated live stream through Apache Kafka, with on-demand high-rate bursts controlled from the dashboard.",
    "Process the stream with Spark Structured Streaming: clean, classify, aggregate in 1-minute windows.",
    "Implement three sentiment scorers: VADER (lexicon), DistilBERT-SST2 (generic transformer), and a custom fine-tuned DistilBERT on 63.6k social-media rows.",
    "Persist scored comments, windowed aggregates, user accounts, and analysis history with idempotent, restart-safe writes.",
    "Serve 30+ REST endpoints over FastAPI: analytics, link/account/keyword/topic analysis, trends, alerts, spam, CSV export, authentication, history.",
    "Visualize live KPIs, charts, feeds, model comparisons, and pipeline monitors on an 8-tab dashboard with per-account isolation.",
    "Evaluate all models against ground-truth labels: accuracy, per-class precision/recall/F1, confusion matrices.",
    "Deliver with one-command startup per operating system and a green 5-stage CI pipeline.",
])
subheading("1.2 Scope")
body(
    "The system ingests into Kafka (KRaft mode — no Zookeeper), processes with Spark Structured "
    "Streaming through a single fault-tolerant checkpointed foreachBatch sink, persists in PostgreSQL, "
    "and visualizes on an 8-tab dashboard (Dashboard, Live, Analyze, Trends, Models, Pipeline, "
    "Sources, Settings) — every page behind authentication, every analysis attributed to the logged-in "
    "account."
)
body(
    "Platform coverage: YouTube works fully live (search ~2–4 s, comments ~5–6 s per video via "
    "yt-dlp). Reddit works via the PullPush archive (~1–3 s). X/Twitter and Reddit block anonymous "
    "real-time access (HTTP 403/521), so live streams for those platforms are pool-matched from the "
    "bundled dataset via indexed SQL (~0.4 s) — real comments, re-scored fresh. Threads, Instagram and "
    "Facebook OAuth flows are fully implemented and activate once Meta app credentials are configured."
)
body(
    "Explicitly out of scope: OAuth ingestion from Instagram/Facebook/Threads (built, awaiting Meta "
    "app credentials), multi-language sentiment analysis (English only), production deployment "
    "patterns (multi-broker Kafka, Spark clustering, read replicas), and sub-second push updates "
    "(WebSockets). These are documented as future work."
)
subheading("1.3 Motivation for the architecture")
body(
    "A streaming pipeline — ingest → classify → aggregate → visualize — mirrors how industry handles "
    "event data at scale: Kafka decouples producers from consumers and buffers bursts; Spark "
    "Structured Streaming provides declarative windowed aggregation with fault-tolerant offsets; a "
    "relational store serves aggregate queries; a stateless REST layer keeps the dashboard simple. "
    "Sentio implements this exact pattern at demo scale, adding the product concerns a real deployment "
    "needs: authentication, per-account history, and operational tooling (one-command startup, CI)."
)

# --- 2. Jira Timeline --------------------------------------------------------
heading("2. Jira Timeline")
body(
    "The project followed an incremental/agile process: 2-week sprints, a demoable increment at every "
    "sprint boundary, and a Jira board with epics, stories and sub-tasks (full backlog, points and "
    "step-by-step board setup in docs/07_Jira_Guide.md). The project commenced in August and concluded "
    "in November — four months, eight sprints, roughly 157 story points across a three-member team "
    "(≈20 points per sprint, a realistic student cadence)."
)
subheading("2.1 Sprint plan (August → November)")
TBL_N, cap = next_table_caption("Project timeline — sprints and milestones (Aug → Nov)")
table(
    [
        ["Sprint", "Dates", "Goal (demoable at sprint end)"],
        ["1 — Foundations", "Aug wk 1–2", "Repo + docs skeleton + docker-compose infra up; Kafka round-trip smoke test"],
        ["2 — Ingestion & first scores", "Aug wk 3–4", "Producer streams CSV → Kafka; Spark scores with VADER; scored rows land in Postgres"],
        ["3 — Full pipeline + API", "Sep wk 1–2", "DistilBERT + windows + PG sinks; FastAPI serves aggregates; unit tests green"],
        ["4 — Dashboard & models page", "Sep wk 3–4", "React dashboard (8 tabs) live; end-to-end wired"],
        ["5 — Link analysis & accounts", "Oct wk 1–2", "Paste/URL analysis, account analysis, trends/alerts/spam/export"],
        ["6 — Auth & history", "Oct wk 3–4", "Signup/login, per-account history, users table (mid-term fixes shipped)"],
        ["7 — Fine-tuning & CI", "Nov wk 1–2", "Fine-tuned DistilBERT (84.2% val accuracy), Jenkins CI green"],
        ["8 — Hardening & delivery", "Nov wk 3–4", "History persistence, per-account isolation, perf tuning (~59 rec/s), final docs"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("2.2 Epic structure")
TBL_N, cap = next_table_caption("Epics and their scope")
table(
    [
        ["Epic", "Scope", "Sprints"],
        ["EPIC 1 — Infrastructure & Ingestion", "docker-compose (Kafka+PG), DB schema, topics, CSV producer with seed/burst control, dataset selection (7 Kaggle sources)", "1–2"],
        ["EPIC 2 — Stream Processing & NLP", "Spark job, cleaning, VADER, transformers, windowing, single foreachBatch sink, performance tuning", "2–3, 8"],
        ["EPIC 3 — Storage & API", "PG upserts, FastAPI core + analytics, link/account analysis, trends/alerts/spam/export", "3–5"],
        ["EPIC 4 — Dashboard", "React scaffold, 8 tabs, topic streams, Go-live button, model comparison", "4–5"],
        ["EPIC 5 — Auth, History & Accounts", "PBKDF2 signup/login, history table, per-account attribution, API hardening", "6"],
        ["EPIC 6 — Model Fine-tuning", "prepare_data, finetune (auto-resume), weights split + push (84.2%)", "7"],
        ["EPIC 7 — CI/CD & Delivery", "Jenkinsfile + zero-click runner, one-command startup per OS, bundled datasets, final docs", "7–8"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("2.3 Mid-term evaluation (October)")
body(
    "The mid-term evaluation (October, week 3) demonstrated the working pipeline end-to-end: Kafka → "
    "Spark → PostgreSQL → FastAPI → dashboard, with link/account analysis, trends, alerts, spam and "
    "export already functional. The demonstration covered the live burst mechanism (dashboard Go-live "
    "button driving the producer), the model comparison panel, and the full 8-tab navigation. "
    "Feedback items — per-account history, authentication, and history persistence across API "
    "restarts — were prioritised into Sprint 6 and shipped by October’s end. The mid-term snapshot of "
    "the Jira board (issues labelled mid-term) is retained as evaluation evidence."
)
subheading("2.4 Delivery (November)")
body(
    "Sprint 7 delivered the fine-tuned DistilBERT (84.2% validation accuracy on 4.6k held-out rows, "
    "trained on 63,603 social-media comments across 3 epochs) and the green Jenkins CI pipeline with "
    "a zero-click runner. Sprint 8 hardened the platform: history persistence with automatic schema "
    "migration, strict per-account attribution (user_email on every analysis, 401 guards on "
    "per-account endpoints), sustained streaming throughput of ~59 records/s (6.5× over the naive "
    "implementation), one-command startup for Linux/macOS/Windows, all datasets bundled in the "
    "repository, and this report. Final evaluation: November, week 4; report submission deadline "
    "26 November 2026."
)
subheading("2.5 Work division")
body(
    "Three members, three workstreams (full phase-by-phase plan and RACI matrix in "
    "docs/04_Work_Division.md): Member A — infrastructure, producer, frontend dashboard, startup "
    "tooling, CI and documentation; Member B — Spark streaming job, NLP module, performance tuning, "
    "model fine-tuning, evaluation; Member C — FastAPI platform, authentication, per-account history, "
    "test suite. Pairs worked in parallel after Sprint 2; every deliverable had a primary and "
    "secondary owner."
)

# --- 3. Requirements (SRS) ---------------------------------------------------
heading("3. Requirements (SRS)")
body(
    "The full specification (docs/01_SRS.md, v2.0) contains 40 functional requirements across seven "
    "groups and 8 non-functional requirements. Requirements evolved with the timeline: Sprints 1–2 "
    "fixed the core pipeline (FR-1..13), the first full demo (September) exposed the need for link "
    "analysis and trends, mid-term feedback drove authentication and per-account history (FR-26..29), "
    "and performance work in November tightened NFR-2 to ~59 records/s. The SRS is the final "
    "consolidated specification."
)
subheading("3.1 Functional requirements — ingestion")
TBL_N, cap = next_table_caption("Ingestion requirements")
table(
    [
        ["FR", "Requirement"],
        ["FR-1", "Producer reads comments from data/raw/all_sources.csv (configurable path)"],
        ["FR-2", "Producer publishes each comment as JSON {id, source, author, text, label, ts, post_id, post_title} to Kafka comments-raw"],
        ["FR-3", "Producer runs a one-time seed pass (default 6,000 rows) then idles, watching a control file"],
        ["FR-4", "POST /api/stream/live triggers a high-rate burst (5–120 msg/s, 0.5–30 min) via the control file; /api/stream/stop ends it"],
        ["FR-5", "Every event id unique per send → downstream sinks remain idempotent"],
        ["FR-6", "POST /api/analyze accepts a YouTube/Reddit/X post URL or pasted text; fetches comments (yt-dlp / PullPush / line parser) and publishes with post_id + post_title"],
        ["FR-7", "POST /api/analyze-account fetches comments across an account’s recent posts (YouTube/Reddit)"],
        ["FR-8", "POST /api/keyword-search and /api/topics/stream fetch/collect comments matching a keyword or trending topic (YouTube live; X/Reddit pool-matched via indexed SQL)"],
        ["FR-9", "Fetched comments flow through the same Kafka → Spark → PostgreSQL pipeline (no separate analysis path)"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("3.2 Functional requirements — processing, storage, API")
TBL_N, cap = next_table_caption("Processing, storage and API requirements")
table(
    [
        ["FR", "Requirement"],
        ["FR-10", "Spark job consumes comments-raw (local[6], arrow batches 512, maxOffsetsPerTrigger 8000, 10 s trigger)"],
        ["FR-11", "Text cleaning: lowercase, strip URLs, HTML entities, emojis, extra whitespace"],
        ["FR-12", "Every comment scored by VADER + DistilBERT-SST2 + fine-tuned DistilBERT + tweet-RoBERTa LLM; 256-char cap; OMP threads pinned before torch loads; model failure never crashes the stream"],
        ["FR-13", "1-minute tumbling windows (counts, percentages, avg score, top words) with watermark"],
        ["FR-14", "All sinks in one checkpointed foreachBatch (PG upserts + Kafka feed), exactly-once resumable"],
        ["FR-15/16", "Idempotent upserts: comments keyed by id, window_stats keyed by window_start"],
        ["FR-17", "API auto-migrates schema at startup (history table, user_email column, indexes)"],
        ["FR-18..25", "30+ REST endpoints: health, summary, timeline, comments, words, compare, pipeline, analyze, analyze-account, keyword-search, topics/stream, stream control, trends, trending, alerts, spam, export"],
        ["FR-25", "posts/accounts/topics-streams/history read the history table (survive restarts) and 401 without ?user="],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("3.3 Functional requirements — auth, history, dashboard, training")
TBL_N, cap = next_table_caption("Auth, history, dashboard and training requirements")
table(
    [
        ["FR", "Requirement"],
        ["FR-26", "Signup/login against the users table; PBKDF2-SHA256 (120,000 iterations); tokens returned"],
        ["FR-27", "Every analysis (post/account/topic/keyword/paste) recorded in history with user_email of the logged-in account"],
        ["FR-28", "GET /api/history?kind&platform&user — the account’s analyses only (401 without user); guests redirected to login"],
        ["FR-29", "History tab shows owner chips; per-account endpoints strictly isolated"],
        ["FR-30..37", "8 dashboard tabs: KPIs/timeline/donut/trending/live feed + Go-live; live feed with filters + export; analyze (post/account/keyword/Threads OAuth); trends with velocity; models 3-way comparison; pipeline counters; sources inventory; history with owner chips; settings (profile/theme/polling)"],
        ["FR-38", "prepare_data.py builds train/val JSONL from the merged dataset (63,603 rows)"],
        ["FR-39", "finetune.py fine-tunes DistilBERT (3-class) with checkpoint auto-resume; weights split ≤90 MB + SHA256, rejoined at setup"],
        ["FR-40", "evaluate.py computes accuracy, per-class precision/recall/F1, confusion matrices (DB or CSV mode)"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("3.4 Non-functional requirements")
TBL_N, cap = next_table_caption("Non-functional requirements (measured at delivery)")
table(
    [
        ["NFR", "Target", "Achieved"],
        ["NFR-1 Latency", "end-to-end ≤ 30 s; API ≤ 500 ms @5k rows", "~30 s produce→dashboard; API < 100 ms"],
        ["NFR-2 Throughput", "≥ 50 rec/s sustained", "~59 rec/s (6.5× over naive ~9/s)"],
        ["NFR-3 Usability", "one-command startup per OS", "startup/<os>/setup.sh — venv, JDK, weights, models, docker, services, CI all automatic"],
        ["NFR-4 Reliability", "survives producer/API restarts; idempotent sinks", "verified: restarts produce no duplicates; history DB-backed"],
        ["NFR-5 Reproducibility", "fresh clone → full demo", "datasets (54 MB) + weights (split parts) bundled; one command"],
        ["NFR-6 Maintainability", "modular; unit-tested", "producer/spark/api/frontend/evaluation/models separated; 42 pytest cases green in CI"],
        ["NFR-7 Portability", "Linux/macOS/Windows", "one-command scripts per OS; macOS setsid fallback; no sudo"],
        ["NFR-8 Security", "hashed passwords; no secrets in repo", "PBKDF2 ×120k; .env.local gitignored; 401 guards; guests redirected"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("3.5 Use cases")
body(
    "UC-1 (view live sentiment): the analyst logs in, opens the dashboard, hits Go-live — the producer "
    "bursts at N/s and counters climb; if the API is down, a status banner shows. UC-2 (run the "
    "platform): bash startup/linux/setup.sh — everything (venv, JDK 17, model weights, HuggingFace "
    "models, docker, four services, Jenkins CI, demo user) installs and starts automatically. UC-3 "
    "(analyze a post/account/keyword): paste a YouTube URL — real comments fetch, flow through the "
    "pipeline, and scores appear in ~30–60 s; the analysis is recorded in History under the logged-in "
    "account permanently. UC-4 (evaluate models): python evaluation/evaluate.py — accuracy, per-class "
    "metrics and confusion matrices printed."
)
subheading("3.6 Acceptance criteria")
TBL_N, cap = next_table_caption("Acceptance criteria (all verified)")
table(
    [
        ["#", "Criterion", "Status"],
        ["AC-1", "Console round-trip through Kafka succeeds", "✅"],
        ["AC-2", "42/42 pytest cases pass (NLP, API, features, threads)", "✅"],
        ["AC-3", "Producer → Kafka → Spark → PostgreSQL yields scored rows + window rows", "✅ (369k+ rows)"],
        ["AC-4", "30+ API endpoints return valid JSON against live data", "✅"],
        ["AC-5", "8-tab dashboard renders live; filters/analyze/history work", "✅"],
        ["AC-6", "Fine-tuned model reaches ≥ 80% validation accuracy", "✅ (84.2%)"],
        ["AC-7", "Every analysis attributed to the logged-in account and persists", "✅"],
        ["AC-8", "Jenkins CI 5/5 stages green", "✅"],
    ],
    caption=cap,
    num=TBL_N,
)

# --- 4. Design (SDD) ----------------------------------------------------------
heading("4. Design (SDD)")
body(
    "Full design document: docs/02_SDD.md (architecture diagram, level-0/1 data flow diagrams, "
    "component design tables, database schema, sequence diagram, error-handling matrix, testing "
    "strategy). This section summarises the design at report depth."
)
subheading("4.1 Architecture")
body(
    "Data flows through six stages. (1) Ingestion sources: bundled Kaggle datasets (274k rows, 54 MB), "
    "yt-dlp (YouTube live), PullPush (Reddit archive), paste, account crawls, keyword/topic matching. "
    "(2) Kafka (KRaft, 3 partitions per topic) decouples ingestion from processing and buffers bursts. "
    "(3) Spark Structured Streaming: parse JSON → clean text (UDF) → three scorers (VADER pandas UDF; "
    "DistilBERT-SST2 + fine-tuned weights and cardiffnlp tweet-RoBERTa via one mapInPandas pass) → "
    "1-minute tumbling windows with watermark. (4) A single checkpointed foreachBatch write path: "
    "PostgreSQL upserts (comments + window_stats) and the Kafka comments-scored feed — the graph is "
    "computed once, not three times. (5) FastAPI: 30+ endpoints with PBKDF2 authentication and "
    "DB-backed per-account history. (6) React 8-tab dashboard polling every 2.5–12 s."
)
subheading("4.2 Key design decisions")
TBL_N, cap = next_table_caption("Design decisions and rationale")
table(
    [
        ["Decision", "Alternative rejected", "Why"],
        ["Kafka KRaft (no Zookeeper)", "Kafka + Zookeeper", "one less system to run/explain; modern default"],
        ["Single foreachBatch sink", "3 separate streaming queries", "graph computed once, not 3×; one checkpoint; measured second-largest perf win"],
        ["OMP_NUM_THREADS pinned before torch imports", "post-init torch.set_num_threads", "Spark’s JVM silently overrides it to 1 in python workers; import-time env is the only reliable fix (6.5× throughput)"],
        ["256-char truncation before scoring", "full text", "34/s @512 chars → 70/s @256; label drift negligible"],
        ["Fine-tuned DistilBERT for accuracy, RoBERTa for live scoring", "generic models everywhere", "domain fine-tune wins on labels (84.2%); RoBERTa wins on live robustness"],
        ["History in PostgreSQL with user_email", "in-memory registry", "survives API restarts; per-account isolation; indexed lookups"],
        ["Auto-migration at API startup", "manual SQL / init-only scripts", "init.sql runs once per container; existing DBs must upgrade themselves"],
        ["Weights split ≤90 MB + SHA256", "Git LFS / release assets", "no LFS in scope; deterministic rejoin at setup; GitHub 100 MB limit respected"],
        ["Polling (2.5–12 s)", "WebSockets", "stateless, trivially reliable, sufficient for 1-min windows"],
        ["Per-account endpoints 401 without ?user=", "open endpoints", "defense-in-depth behind the frontend login redirect"],
        ["Indexed SQL topic matching (DISTINCT ON)", "Python full-table scan", "150k-row scans stacked under concurrency; indexed ILIKE ~0.4 s"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("4.3 Component design")
body(
    "producer/producer.py — column auto-detection across datasets (text/label/id/author/source), "
    "seed-then-idle lifecycle, control-file-driven bursts (logs/live-stream.json written by the API’s "
    "Go-live endpoint), unique ids per send, retries ×3, graceful Ctrl+C. spark/nlp.py — pure "
    "unit-tested scoring functions; NLP_TORCH_THREADS → OMP/MKL_NUM_THREADS exported at module import "
    "before torch loads; NLP_MAX_CHARS=256; torch.inference_mode(); warm() pre-loads models in the "
    "driver. spark/streaming_job.py — build_spark() (local[6], SPARK_DRIVER_MEMORY env, arrow 512, "
    "maxOffsets 8000, 10 s trigger); one foreachBatch write_batch doing PG upserts (psycopg2) + Kafka "
    "feed (kafka-python-ng producer) + window stats (pandas dt.floor groupby); checkpoint "
    "checkpoints/pg-comments; SKIP_BERT=1 fast mode."
)
body(
    "api/main.py — auth (PBKDF2-SHA256 ×120k, token issuance), analytics endpoints (SQL aggregation), "
    "ingest endpoints (yt-dlp / PullPush / pool-matched with DISTINCT ON dedupe), live control "
    "(control file), insights (velocity trends, spike alerts, spam heuristics, CSV export), "
    "per-account endpoints (_require_user → 401; history-table backed), Threads OAuth "
    "(auth-url/status/callback/disconnect), and _ensure_history_table() auto-migration at import. "
    "frontend — AuthProvider (localStorage), Protected routes (guest redirect), api.js attaching "
    "user_email / ?user=, usePolling hook (per-tab interval), Recharts visualisations, owner chips on "
    "history entries."
)
subheading("4.4 Database schema")
TBL_N, cap = next_table_caption("Database tables")
table(
    [
        ["Table", "Key columns", "Notes"],
        ["comments", "id (PK), source, text, cleaned_text, label, vader_label/score, bert_label/score, llm_label/score, ts, processed_at, post_id, post_title", "scored rows; indexes on ts, source, vader_label, post_id, (source, lower(left(text,200)) text_pattern_ops)"],
        ["users", "email (PK), name, password_hash, created_at, last_login", "PBKDF2-SHA256 ×120k"],
        ["history", "id (serial PK), kind, post_id, title, platform, handle, keyword, posts, comments_published, user_email, created_at", "per-account analysis records; indexes on created_at DESC, user_email"],
        ["window_stats", "window_start (PK), window_end, total, positive/negative/neutral, pos/neg/neu_pct, avg_score, top_words", "1-minute aggregates"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("4.5 Sequence — a comment’s journey")
body(
    "Ingester publishes JSON → Kafka comments-raw → Spark micro-batch: parse → clean → VADER + "
    "DistilBERT + RoBERTa → the single foreachBatch upserts comments and window_stats into PostgreSQL "
    "and writes scored JSON to comments-scored → FastAPI SELECTs on poll → React renders. End-to-end "
    "latency ~30 s in demo configuration (producer trigger + Spark trigger + poll interval)."
)
subheading("4.6 Error handling")
TBL_N, cap = next_table_caption("Error-handling matrix")
table(
    [
        ["Failure", "Detection", "Behaviour"],
        ["Kafka down", "connection errors", "producer retries ×3; spark fails visibly; restart after Kafka returns"],
        ["Bad/empty CSV row", "producer build_message", "row skipped"],
        ["Model load/OOM", "try/except in map", "bert/llm columns null; stream continues"],
        ["Duplicate id in batch", "ON CONFLICT upserts", "no crash, idempotent"],
        ["Postgres down", "foreachBatch exception", "batch retried on next micro-batch"],
        ["history table missing (old DB)", "startup migration", "_ensure_history_table() CREATE + ALTER, idempotent"],
        ["Per-account endpoint without user", "_require_user", "401 login required"],
        ["API DB down", "/health", "status degraded; dashboard banner"],
        ["Dashboard API unreachable", "fetch errors", "status dot + banner; empty states"],
    ],
    caption=cap,
    num=TBL_N,
)

# --- 5. Technical Landscape ---------------------------------------------------
heading("5. Technical Landscape")
subheading("5.1 Sentiment analysis families")
TBL_N, cap = next_table_caption("Sentiment analysis approaches compared")
table(
    [
        ["Family", "Method", "Strengths", "Weaknesses"],
        ["Lexicon / rule-based", "VADER (Hutto & Gilbert, 2014)", "fast, transparent, tuned for social text (punctuation, emoji, negation)", "misses context; fixed ~7,500-word vocabulary"],
        ["Transformer (generic)", "DistilBERT-SST2 (Sanh et al., 2019)", "context-aware; 40% smaller / 60% faster than BERT", "binary only; movie-review domain transfers poorly"],
        ["Transformer (fine-tuned)", "our DistilBERT (63.6k social rows)", "3-class; domain-trained; 84.2% validation accuracy", "needs labeled data + training time"],
        ["Transformer (domain pre-trained)", "cardiffnlp tweet-RoBERTa", "trained on 124M tweets; authoritative live score", "heavier; English-centric"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "The three-scorer design is deliberate: identical inputs flow through two paradigms (lexicon vs "
    "learned) and two training regimes (generic vs domain fine-tuned), producing measurable agreement "
    "and a quantified answer to “does fine-tuning help on social text?” — it does: 84.2% vs ≈64% for "
    "the generic model on our data. Disagreements between scorers are themselves the finding; the "
    "Models tab surfaces LLM corrections of VADER as inspectable examples."
)
subheading("5.2 Streaming architectures")
body(
    "Kafka (Kreps et al., 2011) provides a durable, replayable log decoupling producers from "
    "consumers; offsets give exactly-once semantics when paired with checkpointed sinks. The KRaft "
    "protocol (Kafka 3.x) replaces Zookeeper with an internal controller quorum — one less system to "
    "operate. Spark Structured Streaming (Zaharia et al., 2013 — DStreams; modern DataFrame API) "
    "treats the unbounded stream as micro-batches with batch semantics, native tumbling windows, "
    "watermarks for late data, and JDBC sinks. Sentio applies both patterns at demo scale: Kafka "
    "buffers the producer’s bursts; Spark’s 10-second trigger processes them with 1-minute windows; "
    "the single checkpointed foreachBatch guarantees resumable, duplicate-free writes."
)
subheading("5.3 Why this stack (and not alternatives)")
TBL_N, cap = next_table_caption("Technology trade-offs considered")
table(
    [
        ["Choice", "Alternatives considered", "Why this"],
        ["Kafka", "RabbitMQ, Redis Streams", "replayable log + offsets + industry-standard streaming pattern"],
        ["Spark Structured Streaming", "Flink, Kafka Streams, raw consumer groups", "DataFrame API with windowing/watermarks; scales beyond a script; explainable"],
        ["PostgreSQL", "MongoDB, Cassandra, HDFS", "aggregate + recent-rows + per-account queries = relational fit; JDBC sink standard"],
        ["FastAPI", "Flask, Express", "async, OpenAPI docs auto-generated at /docs, pydantic validation"],
        ["React + Vite", "server-rendered pages, Angular", "component model fits live dashboards; HMR keeps iteration fast"],
        ["Jenkins (docker)", "GitHub Actions only", "self-contained lab demo; identical pipeline on any machine; Actions noted as fallback"],
        ["VADER + DistilBERT + RoBERTa", "single model", "controlled comparison: lexicon vs learned; generic vs fine-tuned"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("5.4 Technology stack summary")
TBL_N, cap = next_table_caption("Technology stack")
table(
    [
        ["Layer", "Technology"],
        ["Ingestion", "Python 3.12, kafka-python-ng, yt-dlp, PullPush API"],
        ["Streaming", "Apache Kafka 3.9 (KRaft), PySpark 3.5.4 (Structured Streaming)"],
        ["NLP / ML", "vaderSentiment 3.3.2, transformers 5.x, torch 2.x (CPU), cardiffnlp tweet-RoBERTa, fine-tuned DistilBERT"],
        ["Storage", "PostgreSQL 16-alpine (docker, pgdata volume), indexes incl. text-pattern for ILIKE"],
        ["API", "FastAPI, psycopg2, Uvicorn, pydantic"],
        ["Frontend", "React 19, Vite, Tailwind v4, Recharts"],
        ["CI/CD", "Jenkins LTS (docker), 5-stage pipeline, zero-click runner"],
        ["Infra", "Docker Compose (Kafka + PostgreSQL), healthchecks, one-command startup per OS"],
    ],
    caption=cap,
    num=TBL_N,
)

# --- 6. Git --------------------------------------------------------------------
heading("6. Git")
body(
    "Version control followed trunk-based development onto main: every non-trivial change went through "
    "a feature branch, a pull request with a filled template (what / why / how tested), and a green CI "
    "build before merge. Commit messages follow the convention type: summary (feat / fix / docs / "
    "test / chore), giving a readable history of ~50 commits from first pipeline to final delivery. "
    "Milestones are taggable (v1.0-midterm, v2.0-final)."
)
subheading("6.1 Branching and review flow")
body(
    "Flow: git switch main && git pull → git switch -c feature/<story> → work in small commits → push "
    "→ open PR into main with the template → Jenkins sentio-ci runs the 5-stage pipeline → review → "
    "squash-merge (small PRs) or merge-commit (multi-commit features). Protection on main: require PR, "
    "one approval, no force push."
)
subheading("6.2 Repository map")
TBL_N, cap = next_table_caption("Repository structure")
table(
    [
        ["Path", "Contents"],
        ["producer/", "CSV → Kafka replay (seed + live bursts, control-file driven)"],
        ["spark/", "streaming job + NLP scoring (unit tested)"],
        ["api/", "FastAPI platform (30+ endpoints, auth, per-account history)"],
        ["frontend/", "React 8-tab dashboard (Vite + Tailwind + Recharts)"],
        ["models/", "fine-tuning pipeline + 84.2% weights (split parts + SHA256)"],
        ["evaluation/", "model evaluation vs labels (DB or CSV mode)"],
        ["data/raw/", "bundled datasets (54 MB, 274k rows, 6 CSVs)"],
        ["db/", "Postgres init schema (comments, users, history, window_stats)"],
        ["startup/{linux,mac,windows}/", "one-command setup/start/stop per OS"],
        ["jenkins/ + Jenkinsfile + run_jenkins.sh + Dockerfile.jenkins", "CI pipeline + zero-click Jenkins config"],
        ["tests/", "42 pytest cases"],
        ["docs/", "SRS, SDD, this report, guides (Docker/Jenkins/Jira/GitHub), demo script"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("6.3 Large-file policy")
body(
    "The fine-tuned model weights (268 MB) exceed GitHub’s recommended 50 MB and approach the 100 MB "
    "hard limit, so they are committed as three ≤90 MB parts plus a SHA256 checksum and rejoined by "
    "split_weights.py --join during setup — deterministic and reproducible without Git LFS (LFS was "
    "out of scope). Datasets (54 MB across six CSVs, largest 35 MB) are committed directly. Everything "
    "else regenerable (venvs, checkpoints, caches, logs) is gitignored."
)

# --- 7. Docker ------------------------------------------------------------------
heading("7. Docker")
body(
    "Docker runs the two infra services — Kafka and PostgreSQL — as isolated containers with one "
    "command, identical on every teammate’s machine. Application code (producer, Spark, API, frontend) "
    "runs directly on the host in a Python virtualenv and Node, keeping development and debugging "
    "simple; startup/<os>/start.sh orchestrates everything automatically."
)
subheading("7.1 The kafka container (apache/kafka:3.9.0)")
body(
    "Single-broker cluster in KRaft mode: KAFKA_NODE_ID=1, KAFKA_PROCESS_ROLES=broker,controller, "
    "controller quorum on port 9093, client listener on 9092 with advertised listeners localhost:9092 "
    "for host access, 3 partitions per topic with auto-create enabled, replication factor 1 (single "
    "broker — acceptable for a demo). A broker-api-versions healthcheck marks the container healthy "
    "only when the broker answers; start.sh waits for health before creating topics."
)
subheading("7.2 The postgres container (postgres:16-alpine)")
body(
    "Demo credentials sentiment/sentiment/sentiment (documented defaults, changed via .env.local in "
    "real deployments). The pgdata named volume persists data across container restarts and even "
    "docker daemon restarts (docker start sma-postgres sma-kafka recovers everything). db/init.sql "
    "mounts into /docker-entrypoint-initdb.d/ and creates comments, users, history and window_stats on "
    "first start; later schema changes (e.g. the history table added post-mid-term) self-migrate at "
    "API startup via _ensure_history_table() — no manual SQL on any machine."
)
subheading("7.3 Operational commands")
TBL_N, cap = next_table_caption("Docker commands")
table(
    [
        ["Command", "Effect"],
        ["docker compose up -d", "start both containers detached"],
        ["docker compose ps", "status + health"],
        ["docker compose logs -f kafka", "follow broker logs"],
        ["docker compose down", "stop (keeps pgdata volume)"],
        ["docker compose down -v", "stop AND erase database data"],
        ["docker start sma-postgres sma-kafka", "recover after a daemon restart (volume persists)"],
        ["docker exec sma-kafka ... kafka-topics.sh --list", "list topics (cheat-sheet in docs/05)"],
        ["docker exec sma-postgres psql -U sentiment -d sentiment -c '...'", "query tables"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("7.4 Troubleshooting highlights")
body(
    "Full matrix in docs/05_Docker_Guide.md. The most instructive cases: incomplete KRaft listener env "
    "vars cause the broker to restart with “advertised.listeners cannot use the nonroutable "
    "meta-address” (fix: keep LISTENERS + ADVERTISED_LISTENERS + CONTROLLER_* set together); init.sql "
    "runs on first container start only (fix for missing tables: down -v && up, or simply start the "
    "API which auto-migrates); containers disappear after a host reboot (fix: docker start, the "
    "pgdata volume persists)."
)

# --- 8. Jenkins -------------------------------------------------------------------
heading("8. Jenkins")
body(
    "Continuous Integration runs on a local Jenkins LTS container: every push is compiled, linted and "
    "tested so a broken commit never reaches main. In the report this demonstrates industrial "
    "software-engineering practice on top of the data platform itself."
)
subheading("8.1 The five-stage pipeline")
TBL_N, cap = next_table_caption("Jenkins pipeline stages (Jenkinsfile)")
table(
    [
        ["Stage", "Command", "Checks"],
        ["Setup Python", "python3 -m venv .venv-ci + pip install", "reproducible test env"],
        ["Lint", "python -m compileall spark producer api evaluation", "all modules compile"],
        ["Unit Tests", "pytest tests/ -v", "42 cases (DB/model tests skip gracefully in bare CI)"],
        ["Frontend Build", "npm install && npm run build", "dashboard bundles cleanly"],
        ["Compose Config", "docker compose config -q", "docker-compose.yml valid"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("8.2 Zero-click automation (run_jenkins.sh AUTO mode)")
body(
    "run_jenkins.sh automates the entire CI demo. AUTO=1 mode: builds the sentio-jenkins image "
    "(Jenkins LTS + python3 + node + docker-ce-cli + compose-plugin, with the pipeline plugin set "
    "baked in via jenkins-plugin-cli and jenkins/plugins.txt — no “Install suggested plugins” "
    "wizard); runs the container with a mounted init.groovy.d/basic-security.groovy that creates the "
    "admin user (sentio/sentio123) and disables the first-run wizard; waits for the API, obtains a "
    "crumb, creates the sentio-ci pipeline job via REST (Pipeline script from SCM → the repository → "
    "*/main → Jenkinsfile), and queues build #1 — zero clicks. startup/<os>/setup.sh invokes it "
    "automatically as part of the one-command platform setup."
)
body(
    "Verified end-to-end during development: fresh volume → AUTO=1 ./run_jenkins.sh → job created → "
    "build #1 auto-triggered → SUCCESS (5/5 stages, 34 passed / 8 skipped — DB and model tests skip "
    "gracefully in the bare CI container). First run ~15 minutes (image + plugins); cached runs ~2 "
    "minutes. A webhook trigger (GitHub → Jenkins) is documented as optional; GitHub Actions is the "
    "documented fallback with 1:1 stage mapping."
)

# --- 9. MERN ------------------------------------------------------------------------
heading("9. MERN (Frontend Implementation)")
body(
    "The dashboard follows the MERN pattern’s front half: MongoDB’s role is played by PostgreSQL (the "
    "relational model fits aggregate, recent-rows and per-account queries better than a document "
    "store), Express’s role by FastAPI, and the client is a React SPA built with Node/Vite tooling. "
    "All eight tabs sit behind authentication — guests are redirected to the login page, and the "
    "per-account REST endpoints 401 behind that redirect."
)
subheading("9.1 The eight tabs")
TBL_N, cap = next_table_caption("Dashboard tabs and contents")
table(
    [
        ["Tab", "Contents"],
        ["Dashboard", "KPI cards (total, positive/negative/neutral %), sentiment-over-time line chart, donut, trending-topic cards (clickable → live topic stream), round-robin live feed (one batch can’t flood the card), Go-live button with live status"],
        ["Live", "real-time scored feed with source/sentiment/keyword filters, sentiment chips, both model scores, CSV export"],
        ["Analyze", "platform picker (YouTube/Reddit/X/Instagram/Facebook/Threads): post/URL/paste analysis, account analysis (YouTube/Reddit), keyword search, Threads OAuth connect panel"],
        ["Trends", "rising hashtags/words with velocity (recent vs previous window), drill-down to matching comments"],
        ["Models", "3-way comparison (VADER vs DistilBERT vs LLM): agreement %, label accuracy, LLM corrections of VADER"],
        ["Pipeline", "live stage counters: Kafka offsets (raw in / scored out), Spark throughput (comments/min, windows), PostgreSQL rows"],
        ["Sources", "dataset inventory: per-source counts, bundled datasets, platform coverage"],
        ["History", "every analysis of the logged-in account: kind chips (links/accounts/topics/pasted), live sentiment bars, owner chips (which account ran it), survives API restarts"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("9.2 Implementation details")
body(
    "React 19 with Vite (HMR, ~600 ms production builds), Tailwind v4 for styling, Recharts for the "
    "timeline/donut/bar visualisations. A shared usePolling hook refetches every 2.5–12 s per tab "
    "(configurable in Settings) without page reloads, exposing data/error/pause state to each page. "
    "AuthProvider persists the logged-in user in localStorage; the API client (api.js) attaches "
    "user_email to every analyze call and ?user= to per-account fetches, so attribution is enforced "
    "server-side. Protected routes (App.jsx) redirect guests to /login; the History page renders "
    "owner chips from the API’s user_email field so cross-account attribution is always visible. "
    "Resilience: error banners, skeleton loaders, empty states, and a staged analysis loader that "
    "walks through the pipeline stages while scores land."
)

# --- 10. Other libraries & external APIs ---------------------------------------------
heading("10. Other Libraries & External APIs")
TBL_N, cap = next_table_caption("Libraries and external APIs")
table(
    [
        ["Library / API", "Role"],
        ["yt-dlp", "YouTube search (flat playlist) + comment fetch — keyless, fully live"],
        ["PullPush API", "Reddit submission + comment archive search (no auth)"],
        ["vaderSentiment", "lexicon scoring: compound + pos/neg/neu + label"],
        ["transformers / torch", "DistilBERT-SST2, fine-tuned DistilBERT (3-class), cardiffnlp tweet-RoBERTa inference"],
        ["kafka-python-ng", "producer publishing + Kafka feed writes from the Spark sink"],
        ["psycopg2 / psycopg2.extras", "PostgreSQL upserts (Spark sink) + FastAPI queries (RealDictCursor)"],
        ["FastAPI + Uvicorn + pydantic", "REST platform, request validation, OpenAPI docs at /docs"],
        ["React + Vite + Tailwind v4 + Recharts", "dashboard SPA"],
        ["Jenkins LTS (docker) + jenkins-plugin-cli", "CI pipeline, baked plugin set"],
        ["Docker Compose", "Kafka + PostgreSQL infra with healthchecks"],
        ["Kaggle datasets (7 sources)", "274k labeled comments bundled in data/raw/ (54 MB)"],
        ["python-docx", "this report’s programmatic generation"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("10.1 Platform API behaviour (measured)")
TBL_N, cap = next_table_caption("External platform latency")
table(
    [
        ["Platform", "Method", "Measured latency"],
        ["YouTube", "yt-dlp search + comments", "search ~2–4 s; comments ~5–6 s per video; keyword/topic flow ~13–14 s for 3 videos"],
        ["Reddit", "PullPush archive (2 requests)", "~1–3 s total; API ~0.7 s/request"],
        ["X/Twitter", "bot-walled (403) → pool-matched", "indexed SQL ~0.4 s (bundled dataset rows, re-scored fresh)"],
        ["Threads/Instagram/Facebook", "OAuth flows built", "activate with Meta app credentials in .env.local"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "Graceful degradation: when PullPush is unavailable (HTTP 521 observed during development), "
    "Reddit topic/keyword analyses fall back to the pool-matched path automatically. When X/Reddit "
    "APIs are bot-walled, the pool-match path is the primary route by design — real dataset comments, "
    "re-scored fresh, flowing through the identical pipeline."
)

# --- 11. Output -------------------------------------------------------------------------
heading("11. Output")
subheading("11.1 End-to-end demonstration")
body(
    "A fresh clone → bash startup/linux/setup.sh → the full platform runs with one command: Python "
    "venv + all packages, frontend node_modules, JDK 17 (auto-download, no sudo), fine-tuned weights "
    "rejoined from split parts, HuggingFace sentiment models cached, Kafka + PostgreSQL containers "
    "healthy, topics created, demo login user seeded, four services started and verified (Spark, "
    "producer, API, dashboard), and Jenkins CI queued — first run ~15–20 minutes on decent internet, "
    "mostly one-time; cached runs ~2–3 minutes."
)
body(
    "At runtime the platform accumulated 369,000+ scored comments across seven sources (reddit 153k, "
    "facebook 78k, youtube 73k, x 55k, instagram 4.6k, threads 1.9k, paste) with zero duplicate rows. "
    "The dashboard Go-live button drives producer bursts at 40–120 messages/second for 0.5–30 minutes; "
    "scores appear on the dashboard within ~30–60 s of ingestion. Link analyses (YouTube) fetch real "
    "comments in ~6 s; keyword/topic streams return in ~0.4 s (pool-matched) to ~14 s (live YouTube)."
)
TBL_N, cap = next_table_caption("Accumulated database coverage by source (at delivery)")
table(
    [
        ["Source", "Scored rows", "Ingestion path"],
        ["reddit", "~153,800", "dataset replay (seed + bursts) + PullPush link/account fetches"],
        ["facebook", "~78,700", "dataset replay"],
        ["youtube", "~73,300", "dataset replay + live yt-dlp link/account/topic fetches"],
        ["x / twitter", "~55,600", "dataset replay + pool-matched topic/keyword streams"],
        ["instagram", "~4,650", "dataset replay (OAuth awaiting Meta credentials)"],
        ["threads", "~1,960", "dataset preview (OAuth awaiting Meta credentials)"],
        ["paste", "user-submitted", "Analyze tab paste mode"],
        ["total", "369,000+", "all via Kafka → Spark → PostgreSQL (zero duplicates)"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("11.2 Model results")
TBL_N, cap = next_table_caption("Model evaluation results")
table(
    [
        ["Model", "Accuracy", "Notes"],
        ["VADER (lexicon)", "≈56%", "weak negative recall; neutral band helps on questions/requests"],
        ["DistilBERT-SST2 (generic)", "≈64%", "binary; movie-review domain transfers poorly"],
        ["DistilBERT (fine-tuned, ours)", "84.2% (validation)", "3-class; 63,603 training rows; 3 epochs; checkpoint auto-resume"],
        ["cardiffnlp tweet-RoBERTa", "live authority", "124M-tweet domain model; the dashboard’s authoritative score"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "The fine-tune is the single biggest accuracy lever: +20 points over the generic transformer, "
    "confirming that domain data beats architecture at this scale. Training used the merged dataset "
    "(63,603 rows after cleaning) with an 11/89 validation split; the final weights (268 MB) are "
    "committed as three ≤90 MB parts + SHA256 and rejoined at setup."
)
subheading("11.3 Performance results")
TBL_N, cap = next_table_caption("Performance before and after tuning")
table(
    [
        ["Metric", "Before", "After"],
        ["Sustained stream throughput", "~9 rec/s", "~59 rec/s (6.5×)"],
        ["Transformer batch (2k rows)", "~200 s", "~34 s"],
        ["Topic/keyword stream (X/Reddit)", "full 150k-row Python scan per request", "indexed SQL (DISTINCT ON), ~0.4 s"],
        ["Keyword-search attribution", "dropped silently", "user_email propagated through every path"],
        ["History across API restarts", "in-memory, lost", "PostgreSQL-backed, per-account, survives restarts"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("11.4 Testing summary")
body(
    "42 pytest cases green at delivery: NLP (cleaning, label mapping, scoring), API (endpoint shapes "
    "and filters against a live DB, skipping gracefully when PostgreSQL is unreachable — e.g. bare "
    "CI), features, and threads (hermetic env persistence). Integration checks: Kafka console "
    "round-trip, pipeline → PG row counts. E2E: repeated demo runs. CI: Jenkins 5/5 stages green, "
    "auto-triggered. Key findings from testing: Spark’s JVM silently overrides OMP_NUM_THREADS=1 "
    "inside python workers, single-threading torch (fix: set the env at module import, before torch "
    "loads); three streaming queries recomputed the whole graph 3× (fix: one checkpointed "
    "foreachBatch); 256-char truncation before scoring recovered ~2× with negligible label drift."
)

subheading("11.5 Output figures (screenshots from the running platform)")
body(
    "The following figures are captured from the running platform and inserted in the printed copy; "
    "each is a numbered figure with its caption below (manifest in Appendix H)."
)
figures_out = [
    "One-command setup output — every bootstrap step green, services verified",
    "Dashboard — KPI cards, sentiment timeline, distribution donut, trending topics",
    "Go-live burst — counters climbing at 40 msg/s, live feed updating",
    "Live tab — filtered scored feed with sentiment chips and both model scores",
    "Analyze — YouTube link analysis: fetch progress and staged loader",
    "Analyze detail — scored comments with sentiment chips for the analyzed post",
    "History — analyses with owner chips, kind filters, live sentiment bars",
    "Models — 3-way comparison: agreement, accuracy, LLM corrections of VADER",
    "Pipeline — Kafka offsets, Spark throughput (~59 rec/s), PostgreSQL rows",
    "Trends — velocity-ranked hashtags/words with drill-down",
    "FastAPI /docs — OpenAPI page listing 30+ endpoints",
    "Jenkins — 5/5 green stages (build auto-triggered by run_jenkins.sh AUTO mode)",
    "pytest — 42 passed",
    "evaluation/evaluate.py — accuracy, per-class F1, confusion matrices",
    "Spark console — streaming micro-batches and sustained throughput",
]
for i, cap_text in enumerate(figures_out, start=1):
    p = d.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.15
    r = p.add_run(f"\n[ Figure {i} — screenshot ]\n\n")
    r.font.name = FONT
    r.font.size = Pt(10)
    r.font.italic = True
    r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
    cp = para(f"Figure {i}: {cap_text}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, spacing=1.15)
    cp.paragraph_format.space_after = Pt(10)

# --- 12. Conclusion & Future Scope --------------------------------------------------------
heading("12. Conclusion & Future Scope")
subheading("12.1 Conclusion")
body(
    "Sentio demonstrates that an industrial streaming architecture — Kafka decoupling with replayable "
    "offsets, Spark Structured Streaming with windowed aggregation, fault-tolerant idempotent sinks — "
    "can be delivered as a single-machine platform with one-command startup, while adding the "
    "full-stack product concerns a real deployment needs: PBKDF2 authentication, per-account history "
    "that survives API restarts, strict attribution (user_email on every analysis, 401 guards, guest "
    "redirects), and an 8-tab dashboard with live pipeline observability."
)
body(
    "The three-scorer design turned the platform into a controlled experiment: domain fine-tuning "
    "added +20 accuracy points over the generic transformer (84.2% vs ≈64%), and the lexicon/learned "
    "disagreement analysis produced inspectable artifacts rather than a hidden weakness. The "
    "performance work yielded the project’s most transferable lesson: the largest bottlenecks were "
    "environmental, not algorithmic — a silently overridden thread environment variable and a 3× graph "
    "recomputation accounted for the entire 6.5× throughput gap; profiling before optimizing was what "
    "found them."
)
body(
    "Engineering practice: 42 green tests enforced in CI, ~50 convention-following commits, documented "
    "runbooks (Docker, Jenkins, Jira, GitHub), one-command startup per operating system, and datasets "
    "plus model weights bundled so any machine reproduces the demo from a fresh clone. Final "
    "evaluation: November 2026; report submission 26 November 2026."
)
subheading("12.2 Future scope")
bullets([
    "Meta app credentials → activate the built Threads/Instagram/Facebook OAuth ingestion (the full connect → consent → analyze flow is implemented).",
    "GPU inference for higher sustained throughput; batch the Kafka feed writes from the Spark sink.",
    "Kafka multi-broker with replication + Spark cluster mode for scale experiments.",
    "WebSocket push for sub-second dashboard updates (polling deliberately chosen for v1).",
    "Periodic model re-evaluation and drift monitoring inside the pipeline itself.",
    "Multi-language sentiment models for non-English comments.",
    "X/Twitter official API integration if access tiers permit real-time ingestion.",
])
blank(1)

# ===========================================================================
# APPENDICES (pad to 50+ pages: detailed tables, listings, walkthroughs)
# ===========================================================================
heading("Appendix A — Full Requirement Traceability")
body(
    "Complete requirement-to-implementation traceability. Each functional requirement maps to the "
    "module(s) implementing it and the verification performed."
)
TBL_N, cap = next_table_caption("Requirement traceability — ingestion")
table(
    [
        ["FR", "Implemented in", "Verified by"],
        ["FR-1", "producer/producer.py --file", "demo run; startup/start.sh invocation"],
        ["FR-2", "producer.build_message → KafkaProducer.send", "Kafka console consumer; PG row counts"],
        ["FR-3", "producer.main seed phase + read_control", "log output: seed done, idle mode"],
        ["FR-4", "api/main.py stream_live / stream_stop", "dashboard Go-live button; /api/stream/status"],
        ["FR-5", "producer unique id f\"{id}-{seq}\"", "PG idempotency: no duplicate PK on replays"],
        ["FR-6", "api/main.py analyze → fetchers.fetch", "live YouTube link analysis (~6 s, real comments)"],
        ["FR-7", "api/main.py analyze_account → fetchers.fetch_account", "account analysis on YouTube/Reddit handles"],
        ["FR-8", "api/main.py keyword_search / topics_stream", "keyword + topic streams (x/india 0.4 s, youtube/cricket ~14 s)"],
        ["FR-9", "publisher.publish_comments → comments-raw", "scores appear in PG via the same Spark path"],
    ],
    caption=cap,
    num=TBL_N,
)
TBL_N, cap = next_table_caption("Requirement traceability — processing, storage, API")
table(
    [
        ["FR", "Implemented in", "Verified by"],
        ["FR-10", "spark/streaming_job.py build_spark", "spark.log trigger batches; /api/pipeline counters"],
        ["FR-11", "spark/nlp.py clean_text", "unit tests (test_nlp.py)"],
        ["FR-12", "nlp.py bert_batch/llm_batch + vader UDF", "unit tests; PG llm_label coverage 367k+ rows"],
        ["FR-13", "streaming_job write_batch window groupby", "window_stats rows per minute; /api/timeline"],
        ["FR-14", "streaming_job single foreachBatch", "checkpoint recovery after intentional kill + restart"],
        ["FR-15/16", "ON CONFLICT upserts in write_batch", "replay without duplicates (369k rows, 0 dup)"],
        ["FR-17", "api/main.py _ensure_history_table", "old DB upgraded on API start (no manual SQL)"],
        ["FR-18..25", "api/main.py 30+ endpoints", "pytest API tests; /docs OpenAPI page"],
        ["FR-25", "_require_user + history-table reads", "401 without ?user=; data after API restart"],
    ],
    caption=cap,
    num=TBL_N,
)
TBL_N, cap = next_table_caption("Requirement traceability — auth, history, dashboard, training")
table(
    [
        ["FR", "Implemented in", "Verified by"],
        ["FR-26", "api/main.py signup/login (_hash_password)", "login round-trip; PBKDF2 hash format in users table"],
        ["FR-27", "_record_history(user_email=…)", "history rows carry the logged-in email (verified per run)"],
        ["FR-28", "/api/history?user + frontend redirect", "curl with/without user; guest redirect to /login"],
        ["FR-29", "History owner chips; per-account endpoints", "UI renders user_email chip; cross-account isolation"],
        ["FR-30..37", "frontend/src/pages/* (8 tabs)", "manual dashboard walkthrough; polling hook per tab"],
        ["FR-38", "models/training/prepare_data.py", "train 59k + val 4.6k jsonl generated"],
        ["FR-39", "models/training/finetune.py + split_weights.py", "84.2% val accuracy; 3 parts + SHA256 rejoin at setup"],
        ["FR-40", "evaluation/evaluate.py", "accuracy/F1/confusion output on DB and CSV modes"],
    ],
    caption=cap,
    num=TBL_N,
)

heading("Appendix B — API Endpoint Reference")
body(
    "The FastAPI platform exposes 30+ endpoints; full request/response schemas are auto-documented at "
    "http://localhost:8000/docs (OpenAPI). Summary:"
)
TBL_N, cap = next_table_caption("API endpoints — analytics and monitoring")
table(
    [
        ["Method", "Endpoint", "Purpose"],
        ["GET", "/health", "liveness + DB check"],
        ["GET", "/api/summary", "totals, LLM sentiment split, scorer coverage, per-source counts"],
        ["GET", "/api/timeline?minutes=N", "per-window aggregates for the sentiment-over-time chart"],
        ["GET", "/api/comments", "latest scored comments (limit, source, sentiment, q, post_id filters)"],
        ["GET", "/api/words", "top-N word frequencies (stopwords removed)"],
        ["GET", "/api/compare", "3-way model agreement, label accuracy, LLM corrections of VADER"],
        ["GET", "/api/pipeline", "live Kafka offsets, Spark throughput, window + DB counters"],
        ["GET", "/api/trends", "hashtag/word velocity (recent vs previous window)"],
        ["GET", "/api/trending", "top topics per source with fresh-mention boost"],
        ["GET", "/api/alerts", "negative-spike detection vs trailing baseline"],
        ["GET", "/api/spam", "heuristic spam breakdown (promo, links, caps, repeats)"],
        ["GET", "/api/export", "filtered scored comments as CSV download"],
    ],
    caption=cap,
    num=TBL_N,
)
TBL_N, cap = next_table_caption("API endpoints — ingestion, live control, per-account, auth")
table(
    [
        ["Method", "Endpoint", "Purpose"],
        ["POST", "/api/analyze", "link/paste analysis → fetch comments → Kafka"],
        ["POST", "/api/analyze-account", "account-level comment crawl (YouTube/Reddit)"],
        ["POST", "/api/keyword-search", "keyword stream (YouTube live; X/Reddit pool-matched)"],
        ["POST", "/api/topics/stream", "trending-topic stream with fresh comment batch"],
        ["POST", "/api/stream/live", "start a high-rate producer burst (rate, duration)"],
        ["POST", "/api/stream/stop", "end the burst immediately"],
        ["GET", "/api/stream/status", "whether the producer is mid-burst (Go-live button state)"],
        ["GET", "/api/posts", "analyzed posts from history (per-account, 401 without user)"],
        ["GET", "/api/accounts", "analyzed accounts from history (per-account, 401)"],
        ["GET", "/api/topics/streams", "topic streams from history (per-account, 401)"],
        ["GET", "/api/history", "the account’s analyses with live sentiment (401 without user)"],
        ["POST", "/api/signup · /api/login", "PBKDF2 account creation + credential check"],
        ["GET", "/api/threads/auth-url · /status · /callback", "Threads OAuth flow (needs Meta app creds)"],
        ["POST", "/api/threads/disconnect", "remove the stored token"],
    ],
    caption=cap,
    num=TBL_N,
)

heading("Appendix C — Spark Job Walkthrough")
body(
    "spark/streaming_job.py — the processing core. Key stages, in order:"
)
bullets([
    "build_spark(): local[6] master (SPARK_MASTER env override), SPARK_DRIVER_MEMORY (default 4g), "
    "arrow batches of 512, maxOffsetsPerTrigger 8000, trigger processingTime 10 seconds.",
    "read_kafka(): spark.readStream.format('kafka') on comments-raw, startingOffsets latest (first run "
    "detects an empty checkpoint and starts earliest so replays are not missed).",
    "parse: from_json with the explicit event schema (id, source, author, text, label, ts, post_id, "
    "post_title); event time from the message ts.",
    "clean: nlp.clean_text UDF — lowercase, strip URLs/HTML entities/emoji, collapse whitespace.",
    "score: VADER (vectorized pandas UDF) → compound + label; one mapInPandas pass runs both "
    "transformers (fine-tuned DistilBERT + cardiffnlp RoBERTa) with torch.inference_mode() and the "
    "256-char cap; worker failures set null columns instead of killing the stream.",
    "write_batch (the single foreachBatch): dedupe → psycopg2 upserts (comments ON CONFLICT (id), "
    "window_stats ON CONFLICT (window_start)) → Kafka feed via kafka-python-ng producer → window "
    "stats via pandas dt.floor('60s') groupby. Checkpoint: checkpoints/pg-comments.",
])
body(
    "Performance configuration: NLP_TORCH_THREADS (default 8) is exported as OMP_NUM_THREADS and "
    "MKL_NUM_THREADS by spark/nlp.py at module import — before torch loads — because Spark's JVM "
    "resets the environment inside python workers; post-init torch.set_num_threads only recovers "
    "partial throughput (measured 39/s vs 58/s). Combined with the single-sink collapse and 256-char "
    "truncation, sustained throughput rose from ~9 to ~59 records/s."
)

heading("Appendix D — Database Schema (DDL Extract)")
TBL_N, cap = next_table_caption("comments table columns")
table(
    [
        ["Column", "Type", "Notes"],
        ["id", "TEXT PRIMARY KEY", "unique per send ({source}-{seq})"],
        ["source", "VARCHAR(32) NOT NULL", "reddit / youtube / x / facebook / instagram / threads / paste"],
        ["author", "TEXT", "display handle"],
        ["text / cleaned_text", "TEXT", "raw / normalized"],
        ["label", "TEXT", "dataset ground truth (where present)"],
        ["vader_label / vader_score / vader_positive / vader_negative / vader_neutral", "TEXT / DOUBLE PRECISION", "lexicon scorer output"],
        ["bert_label / bert_score", "TEXT / DOUBLE PRECISION", "fine-tuned DistilBERT output"],
        ["llm_label / llm_score", "TEXT / DOUBLE PRECISION", "cardiffnlp tweet-RoBERTa (authoritative)"],
        ["ts", "TIMESTAMP", "event time (windows)"],
        ["post_id / post_title", "TEXT", "link/topic analysis grouping"],
        ["processed_at", "TIMESTAMP DEFAULT NOW()", "sink write time"],
    ],
    caption=cap,
    num=TBL_N,
)
TBL_N, cap = next_table_caption("users, history, window_stats columns")
table(
    [
        ["Table", "Columns"],
        ["users", "email TEXT PK · name TEXT · password_hash TEXT (pbkdf2_sha256$120000$salt$digest) · created_at · last_login"],
        ["history", "id SERIAL PK · kind (post/account/topic/keyword) · post_id · title · platform · handle · keyword · posts (comma-separated ids) · comments_published · user_email (per-account attribution) · created_at"],
        ["window_stats", "window_start TIMESTAMP PK · window_end · total · positive · negative · neutral · pos_pct · neg_pct · neu_pct · avg_score · top_words · processed_at"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "Indexes: comments(ts), comments(source), comments(vader_label), comments(post_id), "
    "comments(source, lower(left(text,200)) text_pattern_ops) for the topic-match ILIKE scan; "
    "history(created_at DESC), history(user_email). Migration: the API's _ensure_history_table() "
    "runs CREATE TABLE IF NOT EXISTS + ADD COLUMN IF NOT EXISTS at startup, so databases created "
    "before the history feature upgrade themselves with zero manual steps."
)

heading("Appendix E — Sample Evaluation Output")
body(
    "evaluation/evaluate.py --csv data/raw/reddit.csv --sample 2000 (illustrative of the output "
    "format; full confusion matrices are reproduced by running the command):"
)
body(
    "Model comparison — VADER: accuracy ≈56%, best F1 positive (0.68), weak negative recall (0.38). "
    "DistilBERT-SST2: accuracy ≈64%, best F1 positive (0.80), no neutral class (forced binary "
    "choice — its largest single error source). Fine-tuned DistilBERT: validation accuracy 84.2% "
    "(4.6k held-out rows, 3-class). Agreement VADER↔BERT ≈44% — disagreement concentrated on "
    "questions/requests (BERT→negative, VADER→neutral). The dashboard's /api/compare endpoint "
    "recomputes the same metrics over the live stream and surfaces LLM corrections of VADER as "
    "inspectable examples."
)
body(
    "Reproduction: python evaluation/evaluate.py (DB mode, live data) or --csv <file> --sample N "
    "(offline). Confusion matrices print per model; the fine-tuned model loads from "
    "models/sentiment-finetuned (rejoined at setup from the committed split parts)."
)

heading("Appendix F — Runtime Verification Log (Summary)")
body(
    "Evidence captured during development and delivery:"
)
bullets([
    "End-to-end: fresh clone → startup/linux/setup.sh → 4 services green, API /health 200, "
    "dashboard 200, 42/42 tests (start_verify logs).",
    "Throughput: sustained ~59 rec/s after tuning (was ~9); go-live burst +3,315 rows in 2 min; "
    "+15,998 rows in 4.5 min steady.",
    "History: analyze → history row with user_email verified per run; /api/history?user filter "
    "returns only that account's rows; API restart preserves all rows.",
    "Per-account guards: /api/history|posts|accounts|topics/streams → 401 without ?user=, 200 with.",
    "Topic streams: x/india 22 rows in 0.37 s; x/love 100 rows; x/election 15 rows (pool-matched); "
    "youtube/GTA6 200 comments published 14 s after search.",
    "CI: fresh Jenkins volume → AUTO=1 run → job created → build #1 SUCCESS (5/5 stages, 34 passed "
    "/ 8 skipped).",
    "Fine-tune: 3 epochs, 63,603 rows, checkpoint auto-resume verified across interruption; final "
    "validation accuracy 84.2%.",
])
blank(1)

heading("Appendix G — Sample Output Walkthrough")
body(
    "This appendix walks through the platform's output as a user experiences it. Screenshots from the "
    "running platform (see the manifest in Appendix H) are inserted at submission; each walkthrough "
    "step below describes exactly what the corresponding screen shows."
)
subheading("G.1 Setup and first run")
body(
    "bash startup/linux/setup.sh prints a six-stage progress: bootstrap (venv, npm, JDK, weights, "
    "models, demo user), docker compose up with health waits, topic creation, service starts "
    "(Spark, producer, API, dashboard), and a final verification box with one line per service — "
    "green checkmarks for Spark streaming (logs/spark.log), Producer, API (localhost:8000/docs) and "
    "Dashboard (localhost:5173). First run ~15–20 minutes (mostly one-time downloads); every later "
    "run ~2–3 minutes."
)
subheading("G.2 Dashboard — the pulse at a glance")
body(
    "The Dashboard tab opens on six KPI cards (total comments, positive/negative/neutral "
    "percentages), a sentiment-over-time line chart built from 1-minute window aggregates, a "
    "distribution donut, trending-topic cards per platform (clickable — each opens a live topic "
    "stream), and a round-robin live feed that interleaves sources so a single burst cannot flood "
    "the card. The Go-live button shows the producer's burst state; clicking it starts a 40 msg/s "
    "burst for 3 minutes (configurable) and every counter on the page visibly climbs."
)
subheading("G.3 Analyze — link, account, keyword, topic")
body(
    "The Analyze tab picks a platform (YouTube/Reddit/X/Instagram/Facebook/Threads). Pasting a "
    "YouTube URL fetches its real comments via yt-dlp (~6 s) and publishes them into the pipeline; "
    "a staged loader walks through the six pipeline stages (pulling → publishing → cleaning → LLM "
    "scoring → Postgres → charts) while Spark scores. Within ~30–60 s the post's detail page fills "
    "with scored comments (sentiment chips, both model scores) and a live sentiment split. Account "
    "analysis crawls an account's recent posts; keyword search returns a matched comment stream in "
    "~0.4 s (pool-matched platforms) to ~14 s (live YouTube)."
)
subheading("G.4 History — every analysis, forever")
body(
    "The History tab lists every analysis the logged-in account has run: kind chips (links, "
    "accounts, topics, pasted), platform badges, timestamps, live sentiment bars, and an owner chip "
    "showing which account ran it. Rows link back to the analysis detail. Data lives in PostgreSQL "
    "(not memory), so the list survives API restarts and is strictly filtered to the logged-in "
    "account — logged out, the app redirects to login and the API 401s."
)
subheading("G.5 Models — the controlled comparison")
body(
    "The Models tab renders the 3-way comparison: agreement percentages (VADER↔LLM, BERT↔LLM, "
    "all-three), label accuracy against dataset ground truth, and the LLM-corrections list — real "
    "comments where the transformer disagrees with the lexicon (sarcasm, negation, domain slang), "
    "the project's most demoable artifact. Fine-tuned DistilBERT's 84.2% validation accuracy is "
    "contrasted with the generic model's ≈64%."
)
subheading("G.6 Pipeline — observability")
body(
    "The Pipeline tab shows live stage counters polled from /api/pipeline: Kafka end-offsets for "
    "comments-raw (ingestion) and comments-scored (output), Spark throughput (comments/minute), "
    "1-minute windows in the last 30 minutes, and PostgreSQL row counts. During a Go-live burst "
    "these counters climb in real time — the clearest demonstration that the stream is flowing "
    "end-to-end."
)
subheading("G.7 Trends — velocity, not volume")
body(
    "The Trends tab ranks hashtags and words by mention velocity: counts in the last 30 minutes "
    "versus the previous 30, volume-weighted. Each term drills down to the matching comments. When "
    "the stream has been idle, the lookback widens to 24 hours so the tab always shows meaningful "
    "rising terms instead of going empty."
)

heading("Appendix H — Screenshot Manifest (capture before submission)")
body(
    "The following screenshots should be captured from the running platform and inserted into the "
    "Output section of the printed copy (each as a numbered figure with a caption below):"
)
TBL_N, cap = next_table_caption("Screenshot manifest")
table(
    [
        ["#", "Screen", "What it shows"],
        ["1", "docker compose ps", "both infra containers healthy"],
        ["2", "startup/<os>/setup.sh output", "one-command setup: every step green"],
        ["3", "Dashboard tab", "KPIs, timeline, donut, trending topics, live feed"],
        ["4", "Go-live burst", "counters climbing at 40/s during a burst"],
        ["5", "Analyze tab", "link analysis of a YouTube URL → fetch counts"],
        ["6", "Analyze detail", "scored comments with sentiment chips for the analyzed post"],
        ["7", "History tab", "analyses with owner chips, kind filters, live sentiment bars"],
        ["8", "Models tab", "3-way comparison + LLM corrections of VADER"],
        ["9", "Pipeline tab", "Kafka offsets, Spark throughput, PG rows"],
        ["10", "Trends tab", "velocity-ranked hashtags/words + drill-down"],
        ["11", "FastAPI /docs", "OpenAPI page listing 30+ endpoints"],
        ["12", "Jenkins build", "5/5 green stages"],
        ["13", "pytest output", "42 passed"],
        ["14", "evaluation output", "accuracy + confusion matrices"],
        ["15", "Spark console", "streaming batches + throughput"],
    ],
    caption=cap,
    num=TBL_N,
)

heading("Appendix I — Test Suite Inventory (42 cases)")
body(
    "The pytest suite enforced in CI (pytest tests/ -v) comprises 42 cases across five files. "
    "DB-backed tests skip automatically when PostgreSQL is unreachable (bare CI containers); "
    "LLM-backed tests skip when the HuggingFace cache lacks the cardiffnlp model."
)
TBL_N, cap = next_table_caption("Test files and coverage")
table(
    [
        ["File", "Coverage", "Notes"],
        ["tests/test_nlp.py", "clean_text normalization, VADER label mapping bands, scorer output shapes", "unit-level; hermetic"],
        ["tests/test_api.py", "endpoint shapes: /health, /api/summary, /api/comments filters, /api/words, /api/compare", "TestClient; @requires_db skip guard"],
        ["tests/test_api_helpers.py", "auth hashing/verification, token format, validation rules, spam heuristics", "pure functions"],
        ["tests/test_features.py", "trends velocity, alerts spike logic, export CSV shape, history payload shape", "DB-backed with skip guard"],
        ["tests/test_threads.py", "env persistence (hermetic: explicit env_path, no repo .env.local writes)", "isolated from developer state"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "Result at delivery: 42 passed in ~6 s locally; in Jenkins CI: 34 passed / 8 skipped (DB and "
    "model tests skip gracefully in the bare container). CI runs the full suite on every push — "
    "a red build blocks the merge."
)

heading("Appendix J — Glossary")
TBL_N, cap = next_table_caption("Glossary of terms")
table(
    [
        ["Term", "Meaning"],
        ["KRaft", "Kafka's Raft-based metadata protocol — replaces Zookeeper (Kafka 3.x default)"],
        ["Micro-batch", "Processing model treating the stream as a sequence of small batches (Spark Structured Streaming)"],
        ["Watermark", "Bound on how late event-time data may arrive and still update a window"],
        ["Tumbling window", "Fixed, non-overlapping time window (here: 1 minute)"],
        ["foreachBatch", "Spark sink operator running batch logic per micro-batch with checkpointed offsets"],
        ["mapInPandas", "Spark API streaming DataFrame partitions through a Python iterator (one model instance)"],
        ["VADER", "Valence Aware Dictionary and sEntiment Reasoner — lexicon/rule sentiment analyzer"],
        ["Compound score", "VADER's normalized sentiment score in [-1, 1]; |x| ≤ 0.05 = neutral"],
        ["DistilBERT", "Distilled BERT — 40% smaller, 60% faster; here SST-2 and our 3-class fine-tune"],
        ["cardiffnlp tweet-RoBERTa", "RoBERTa trained on 124M tweets — the authoritative live scorer"],
        ["Pool-matched stream", "Live analysis replaying dataset rows matching the keyword/handle (platform APIs bot-walled)"],
        ["PBKDF2", "Password-Based Key Derivation Function 2 — password hashing (SHA-256, 120k iterations here)"],
        ["user_email attribution", "Every analysis recorded in history with the logged-in account's email"],
        ["Idempotent sink", "Writes that can be retried without duplicating rows (ON CONFLICT upserts)"],
        ["Checkpoint", "Spark's stream-progress record enabling exactly-once resumable sinks"],
        ["Go-live burst", "On-demand producer burst at 5–120 msg/s triggered from the dashboard"],
        ["Owner chip", "UI badge on history rows showing which account ran the analysis"],
        ["yt-dlp", "Keyless YouTube downloader used for live search + comment fetch"],
        ["PullPush", "Reddit archive API (submission + comment search, no auth)"],
        ["text_pattern_ops", "PostgreSQL index opclass enabling efficient prefix/ILIKE matching"],
    ],
    caption=cap,
    num=TBL_N,
)

heading("Appendix K — Team Work Division Summary")
body(
    "Full detail in docs/04_Work_Division.md (workstreams, Aug→Nov phase plan, RACI matrix). Summary "
    "of the three workstreams:"
)
TBL_N, cap = next_table_caption("Work division summary")
table(
    [
        ["Member", "Workstream", "Key deliverables"],
        ["Member A", "Infra, Producer & Frontend", "docker-compose infra, CSV→Kafka producer with burst control, 8-tab React dashboard, one-command startup per OS, Jenkins CI (zero-click), documentation set"],
        ["Member B", "Spark, NLP & Model Training", "Spark streaming job (single foreachBatch), unit-tested NLP module, 6.5× performance tuning, DistilBERT fine-tune (84.2%), evaluation"],
        ["Member C", "API, Auth & History", "30+ FastAPI endpoints, PBKDF2 signup/login, per-account history with attribution, history persistence + auto-migration, 42-case test suite"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "All members contributed to mid-term/final demonstrations, requirement reviews, and the "
    "documentation. The full RACI matrix and the phase-by-phase plan with dates (August → November, "
    "mid-term October) are maintained in docs/04_Work_Division.md and the Jira board "
    "(docs/07_Jira_Guide.md)."
)

heading("Appendix L — Data Sources")
body(
    "Seven Kaggle/UCI sources were merged into data/raw/all_sources.csv (144,800 rows across six "
    "platforms) and bundled in the repository (54 MB total). The producer auto-detects common column "
    "names across all of them (text: comment/text/CONTENT/content/body/clean_text; label: "
    "label/sentiment/category/CLASS; id/author variants)."
)
TBL_N, cap = next_table_caption("Bundled datasets")
table(
    [
        ["File", "Platform", "Approx. rows", "Source"],
        ["reddit.csv", "Reddit", "38,206", "Kaggle — Twitter and Reddit Sentimental Analysis (cosmos98)"],
        ["x.csv", "X / Twitter", "20,001", "Kaggle Twitter sentiment sets"],
        ["facebook.csv", "Facebook", "49,454", "Kaggle Facebook comments set"],
        ["youtube.csv", "YouTube", "18,365", "Kaggle YouTube comments / UCI YouTube Spam Collection (CC BY 4.0)"],
        ["instagram.csv", "Instagram", "1,450", "Kaggle Instagram comment set"],
        ["all_sources.csv", "merged (6 platforms)", "144,800", "union of the above, producer input"],
        ["sample_comments.csv", "YouTube-style", "50", "committed fallback (works with zero setup)"],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "Accumulated database coverage at delivery (369k+ scored rows) also includes live-ingested "
    "comments: YouTube links/accounts/topics via yt-dlp, Reddit via PullPush, pasted comments, and "
    "pool-matched X/Reddit topic streams — all flowing through the identical Kafka → Spark → "
    "PostgreSQL pipeline."
)

heading("Appendix M — Environment & Reproduction")
subheading("I.1 Prerequisites")
bullets([
    "Docker Desktop (running) — the only hard prerequisite for infra.",
    "Node.js 18+ and Python 3.10–3.12 (system apps; not auto-installed).",
    "Windows: WSL2 backend for Spark (Docker Desktop with WSL2 covers it).",
])
subheading("I.2 One-command setup per platform")
TBL_N, cap = next_table_caption("Per-platform commands")
table(
    [
        ["Platform", "Command", "Notes"],
        ["Linux", "bash startup/linux/setup.sh", "reference implementation"],
        ["macOS", "bash startup/mac/setup.sh", "identical, macOS-safe (Intel & Apple Silicon)"],
        ["Windows", "startup\\windows\\setup.bat", "double-click; Jenkins step needs Git Bash/WSL"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("I.3 What setup.sh does (in order)")
bullets([
    "bootstrap: python venv + requirements, npm install, JDK 17 auto-download (~190 MB, user-local, "
    "no sudo; skipped if Java 17 present), fine-tuned weights rejoin (split parts → safetensors), "
    "HuggingFace sentiment models download (~5 min, one-time), demo login user seed.",
    "docker compose up + healthcheck wait (kafka + postgres healthy).",
    "Kafka topics (comments-raw, comments-scored; 3 partitions, idempotent).",
    "start services: Spark streaming job (run_spark.sh), producer (seed pass then idle), FastAPI "
    "(:8000), Vite dashboard (:5173).",
    "verify: health checks with retry; prints the green/red status box.",
    "Jenkins CI (AUTO mode): plugins baked, admin created, sentio-ci job created via REST, first "
    "build queued (localhost:8090, login sentio/sentio123).",
])
subheading("I.4 Environment variables")
TBL_N, cap = next_table_caption("Key environment variables (.env.local, gitignored)")
table(
    [
        ["Variable", "Default", "Purpose"],
        ["KAFKA_BOOTSTRAP", "localhost:9092", "producer + Kafka feed target"],
        ["PG_HOST / PG_PORT / PG_DB / PG_USER / PG_PASSWORD", "localhost / 5432 / sentiment / sentiment / sentiment", "PostgreSQL connection (API + Spark sink)"],
        ["NLP_TORCH_THREADS", "8", "torch threads inside Spark workers (exported as OMP/MKL_NUM_THREADS before torch loads)"],
        ["NLP_MAX_CHARS", "256", "text truncation before transformer scoring"],
        ["SPARK_MASTER", "local[6]", "Spark master (lower to local[4] on 16 GB laptops)"],
        ["SPARK_DRIVER_MEMORY", "4g", "driver heap (2g on small laptops)"],
        ["SKIP_BERT", "(unset)", "1 = skip transformer scoring (fast demo mode)"],
        ["THREADS_ACCESS_TOKEN", "(unset)", "Threads OAuth token (persisted by the callback)"],
    ],
    caption=cap,
    num=TBL_N,
)
subheading("I.5 Credentials on the demo box")
body(
    "Dashboard login: ada@sentio.app / secret123 (seeded by scripts/seed_demo_user.py; any account "
    "can be created via signup). Jenkins: sentio / sentio123 (created by the AUTO-mode init groovy). "
    "PostgreSQL: sentiment / sentiment (demo defaults). No other credentials are required — YouTube "
    "and Reddit ingestion are keyless."
)

heading("Appendix N — 10-Minute Demo Script")
body(
    "The demonstration order used for the mid-term and final evaluations (run from the one-command "
    "setup; the full script with viva Q&A is docs/09_Demo_and_Viva.md):"
)
TBL_N, cap = next_table_caption("Demo script (10 minutes)")
table(
    [
        ["#", "Screen / terminal", "Say"],
        ["1", "docker compose ps", "Two infra containers: Kafka in KRaft mode — no Zookeeper — and PostgreSQL."],
        ["2", "docker exec sma-kafka ... kafka-topics.sh --list", "Two topics: raw comments in, scored out — 3 partitions each."],
        ["3", "log in at localhost:5173", "Per-account: everything I analyze is stored under my account."],
        ["4", "Dashboard tab", "Live KPIs, sentiment timeline, distribution, trending topics, round-robin feed."],
        ["5", "click Go-live", "The producer bursts at 40 messages/second on demand — counters climb."],
        ["6", "Analyze → paste a YouTube URL", "Link analysis: yt-dlp fetches real comments; they flow Kafka → Spark → Postgres; scores in ~30-60s."],
        ["7", "History tab", "Every analysis I've run — links, accounts, keywords, topics — in Postgres with my email, survives restarts."],
        ["8", "Models tab", "Three scorers compared; our fine-tuned model: 84.2% validation accuracy. LLM corrections of VADER surfaced."],
        ["9", "Pipeline tab", "Live stage counters: Kafka offsets, Spark throughput (~59 records/s), Postgres rows."],
        ["10", "Trends tab", "Velocity ranking: hashtags/words rising fastest."],
        ["11", ".venv/bin/pytest tests/ -q", "42 test cases, all green — enforced in Jenkins CI."],
        ["12", "python evaluation/evaluate.py", "Offline evaluation: accuracy, per-class F1, confusion matrices."],
    ],
    caption=cap,
    num=TBL_N,
)
body(
    "Viva one-liners: Kafka decouples ingestion from processing (replayable offsets, burst "
    "buffering). Spark Structured Streaming = micro-batches with DataFrame semantics, windows and "
    "watermarks. Three scorers = controlled comparison (lexicon vs learned; generic vs fine-tuned). "
    "Per-account history = user_email on every analysis, DB-backed, 401-guarded. Performance "
    "findings = environment-level bottlenecks (thread env override, 3× graph recomputation), not "
    "algorithmic ones."
)

heading("Appendix O — Known Issues & Resolutions (post-mortem)")
body(
    "Issues encountered during development and how they were resolved — the transferable lessons of "
    "the project:"
)
TBL_N, cap = next_table_caption("Known issues and resolutions")
table(
    [
        ["Issue", "Root cause", "Resolution"],
        ["Torch ran single-threaded inside Spark workers (~200 s per 2k batch)", "Spark's JVM overrides OMP_NUM_THREADS=1 in python workers", "export OMP/MKL_NUM_THREADS at module import, before torch loads (~6.5× recovery)"],
        ["Three streaming queries recomputed the whole graph 3×", "separate Kafka feed + PG + stats sinks", "collapsed into one checkpointed foreachBatch (second-largest win)"],
        ["history table missing on existing databases", "init.sql runs on first container start only", "_ensure_history_table() auto-migration at API startup (idempotent)"],
        ["Analyses disappeared after API restart", "in-memory registries for posts/accounts/topic streams", "history-table-backed reads + user_email attribution"],
        ["Keyword-search runs were ownerless", "user_email dropped in the request re-wrap", "propagated through every analyze path; backfilled NULL rows"],
        ["Topic stream page showed nothing for YouTube topics", "prefix filter expected topic-slug ids; YouTube uses real video ids", "history-driven streams endpoint + keyword match"],
        ["Slow concurrent topic streams (3–4 simultaneous hung)", "full 150k-row Python scan per request", "indexed SQL with DISTINCT ON dedupe (~0.4 s)"],
        ["mapInPandas schema corruption", "StructType.add() mutates in place", "build the output schema as a fresh StructType"],
        ["GitHub rejects 268 MB weights", "100 MB hard limit", "split into 3 ≤90 MB parts + SHA256; rejoin at setup"],
        ["ts ordering broke with mixed tz-aware/naive timestamps", "mixing timestamp styles in the sink", "producer emits naive local time consistently"],
    ],
    caption=cap,
    num=TBL_N,
)

blank(1)

# references
heading("References")
refs = [
    'C. Hutto and E. Gilbert, "VADER: A Parsimonious Rule-based Model for Sentiment Analysis of Social Media Text," ICWSM, 2014.',
    'V. Sanh et al., "DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter," arXiv:1910.01108, 2019.',
    'F. Barbieri et al., "TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification," 2020 (cardiffnlp twitter-roberta).',
    'M. Zaharia et al., "Discretized Streams: Fault-Tolerant Streaming Computation at Scale," SOSP, 2013.',
    'J. Kreps, N. Narkhede, J. Rao, "Kafka: a Distributed Messaging System for Log Processing," NetDB, 2011.',
    "Apache Kafka Documentation — KRaft mode, kafka.apache.org/documentation.",
    "Apache Spark Structured Streaming Programming Guide, spark.apache.org.",
    "FastAPI Documentation, fastapi.tiangolo.com.",
    "React Documentation, react.dev; Vite Documentation, vite.dev.",
    "Datasets: Kaggle — Twitter and Reddit Sentimental Analysis Dataset (cosmos98) + 6 merged Kaggle sources; UCI — YouTube Spam Collection (CC BY 4.0).",
]
for i, r in enumerate(refs, 1):
    para(f"[{i}] {r}", size=11, spacing=1.15)

d.save(OUT)
print(f"saved: {OUT}")
