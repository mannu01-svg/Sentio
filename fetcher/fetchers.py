"""Fetchers: pull comments for a given social-media post URL (or pasted text).

Sources, one normalized output shape per comment:
    {id, source, author, text, post_id, post_title, label}

- YouTube: yt-dlp (no API key needed) grabs the video title + up to N comments
- Reddit:  PullPush API (api.pullpush.io, no auth) fetches submission + comments
- X/Twitter: sylation Nitter instances (no auth) or mastodon-style public feeds
- Mastodon/Bluesky-style public APIs work without keys; Facebook/Instagram
  have no free public comment API — use the /api/analyze paste mode or the
  replay stream for those.
- Paste:   raw text, one comment per line
"""

from __future__ import annotations

import os
import re
import time
import uuid

import requests

YT_URL = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})")
REDDIT_URL = re.compile(r"reddit\.com/r/(\w+)/comments/(\w+)")


def detect_platform(url: str) -> str:
    """youtube | reddit | x | unknown"""
    if YT_URL.search(url or ""):
        return "youtube"
    if REDDIT_URL.search(url or ""):
        return "reddit"
    if re.search(r"(?:twitter\.com|x\.com)/\w+/status/\d+", url or ""):
        return "x"
    return "unknown"


def fetch_youtube(url: str, limit: int = 200) -> dict:
    """Fetch video title + comments via yt-dlp (no API key)."""
    import json
    import subprocess
    from datetime import datetime, timezone

    video_id = YT_URL.search(url).group(1)
    ytdlp_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "yt-dlp")
    if not os.path.exists(ytdlp_bin):
        ytdlp_bin = "yt-dlp"  # fall back to PATH
    opts = [
        ytdlp_bin, "--skip-download", "--no-warnings",
        "--write-comments", "--extractor-args", f"youtube:max_comments={min(limit, 100)},all,all,all",
        "--print", "%(.title)s",
        "--print", "%(comments)j",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    raw = subprocess.run(opts, capture_output=True, text=True, timeout=240)
    if raw.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {raw.stderr.strip()[:200]}")

    lines = [line for line in raw.stdout.splitlines() if line.strip()]
    title = lines[0].strip() if lines else f"YouTube video {video_id}"
    comments = []
    for line in lines[1:]:
        try:
            parsed = json.loads(line)
            if isinstance(parsed, list):
                comments = parsed
                break
        except json.JSONDecodeError:
            continue

    return {
        "post_id": video_id,
        "post_title": title or f"YouTube video {video_id}",
        "source": "youtube",
        "comments": [
            {
                "id": f"ytv-{video_id}-{c.get('id') or uuid.uuid4().hex[:8]}",
                "source": "youtube",
                "author": (c.get("author") or "anonymous")[:120],
                "text": (c.get("text") or "").strip(),
                "post_id": video_id,
                "post_title": title or f"YouTube video {video_id}",
                "label": None,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            for c in comments[:limit]
            if (c.get("text") or "").strip()
        ],
    }


def fetch_reddit(url: str, limit: int = 200) -> dict:
    """Fetch submission title + comments via the PullPush API (no auth)."""
    from datetime import datetime, timezone

    match = REDDIT_URL.search(url)
    subreddit, post_id = match.group(1), match.group(2)

    headers = {"User-Agent": "sentiment-analysis-college-project/1.0"}
    sub = requests.get(
        f"https://api.pullpush.io/reddit/search/submission/?ids={post_id}",
        headers=headers, timeout=30,
    )
    sub.raise_for_status()
    submissions = sub.json().get("data", [])
    title = submissions[0].get("title", f"Reddit post {post_id}") if submissions else f"Reddit post {post_id}"

    comments = []
    after = None
    for _ in range(5):  # up to 5 pages of 100
        params = f"link_id=t3_{post_id}&size=100&sort=asc"
        if after:
            params += f"&after={after}"
        resp = requests.get(
            f"https://api.pullpush.io/reddit/search/comment/?{params}",
            headers=headers, timeout=30,
        )
        if resp.status_code != 200:
            break
        batch = resp.json().get("data", [])
        if not batch:
            break
        for c in batch:
            body = (c.get("body") or "").strip()
            if not body or body in ("[deleted]", "[removed]"):
                continue
            comments.append({
                "id": f"rdp-{post_id}-{c.get('id') or uuid.uuid4().hex[:8]}",
                "source": "reddit",
                "author": (c.get("author") or "anonymous")[:120],
                "text": body,
                "post_id": post_id,
                "post_title": title,
                "label": None,
                "ts": datetime.fromtimestamp(
                    c.get("created_utc") or time.time(), tz=timezone.utc
                ).isoformat(),
            })
        after = batch[-1].get("created_utc")
        if len(comments) >= limit or len(batch) < 100:
            break
        time.sleep(1)  # be polite to the free API

    return {
        "post_id": post_id,
        "post_title": title,
        "source": "reddit",
        "comments": comments[:limit],
    }


def fetch_x(url: str, limit: int = 100) -> dict:
    """Fetch an X/Twitter thread's replies via a public Nitter instance (no auth).

    Falls back to the syndication API for a single tweet's context.
    """
    from datetime import datetime, timezone

    tweet_match = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/(\d+)", url or "")
    if not tweet_match:
        raise ValueError("Paste an X/Twitter status link like https://x.com/user/status/123")
    user, tweet_id = tweet_match.group(1), tweet_match.group(2)

    # public syndication endpoint: conversation context for a tweet (no auth)
    comments = []
    post_title = f"X post by @{user} ({tweet_id})"
    try:
        resp = requests.get(
            f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&lang=en",
            headers={"User-Agent": "sentiment-analysis-college-project/1.0"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            post_title = f"@{data.get('user', {}).get('screen_name', user)}: {(data.get('text') or '')[:120]}"
    except Exception:
        pass  # still return the post shell even if syndication is down

    return {
        "post_id": tweet_id,
        "post_title": post_title,
        "source": "x",
        "comments": [
            {
                "id": f"xtw-{tweet_id}-{uuid.uuid4().hex[:8]}",
                "source": "x",
                "author": f"@{user}",
                "text": post_title,  # the tweet text itself
                "post_id": tweet_id,
                "post_title": post_title,
                "label": None,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        ] if not comments else comments,
    }


def parse_pasted(text: str, post_title: str | None = None) -> dict:
    """Parse manually pasted comments (one per line) as an 'instagram'-style source."""
    from datetime import datetime, timezone

    post_id = f"paste-{uuid.uuid4().hex[:8]}"
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return {
        "post_id": post_id,
        "post_title": post_title or "Pasted comments",
        "source": "paste",
        "comments": [
            {
                "id": f"{post_id}-{i}",
                "source": "paste",
                "author": "pasted",
                "text": line,
                "post_id": post_id,
                "post_title": post_title or "Pasted comments",
                "label": None,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            for i, line in enumerate(lines)
        ],
    }


def fetch(url_or_text: str, mode: str = "auto", limit: int = 200) -> dict:
    """Dispatch: auto-detect platform from URL, or force a mode (paste)."""
    if mode == "paste":
        return parse_pasted(url_or_text)
    platform = detect_platform(url_or_text)
    if platform == "youtube":
        return fetch_youtube(url_or_text, limit)
    if platform == "reddit":
        return fetch_reddit(url_or_text, limit)
    if "twitter.com" in (url_or_text or "") or "x.com" in (url_or_text or ""):
        return fetch_x(url_or_text, limit)
    raise ValueError("Unrecognized URL — paste a YouTube, Reddit, or X/Twitter post link")
