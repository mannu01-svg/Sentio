#!/usr/bin/env python3
"""Lightweight English detection for dataset rows (VADER/BERT are English models).

Heuristic ASCII-ratio + common-word check — cheap and explainable, good enough
to drop Bangla/Indonesian/Thai/Portuguese rows without a heavy dependency.
"""

import re

COMMON = set(
    """the be to of and a in that have i it for not on with he as you do at this but his by from
    they we say her she or an will my one all would there their what so up out if about who get
    which go me when make can like time no just him know take people into year your good some
    could them see other than then now look only come its over think also back after use two how
    our work first well way even new want because any these give day most us love great happy
    thanks thank best better really very much more going got don didn isn isn't it's i'm
    mental health matters break life feel feeling need need help help world today always never
    thing things try start stop keep let put call turn follow watch read listen play enjoy
    everything something anything nothing everyone someone family friend school home city money
    health happy sad angry afraid excited tired funny beautiful amazing awesome terrible awful
    climate action fitness service product quality price order buy sell online free sale""".split()
)

WORD_RE = re.compile(r"[a-zA-Z']+")


def is_english(text: str, threshold: float = 0.35) -> bool:
    """True if the text looks English: mostly ASCII + some common English words."""
    t = (text or "").strip()
    if not t:
        return False
    printable = sum(1 for c in t if c.isascii() and (c.isalnum() or c.isspace() or c in ".,'!?-#"))
    if printable / len(t) < 0.85:
        return False
    words = [w.lower() for w in WORD_RE.findall(t)]
    if len(words) < 3:
        return False
    hits = sum(1 for w in words if w in COMMON or len(w) <= 4)
    return hits / len(words) >= threshold
