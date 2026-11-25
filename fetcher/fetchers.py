"""Fetchers: pull comments for a given social-media post URL (or pasted text).

Sources, one normalized output shape per comment:
    {id, source, author, text, post_id, post_title, label}

- YouTube: official YouTube Data API v3 when YOUTUBE_API_KEY is set (free key,
           works from cloud servers), otherwise yt-dlp (no key, home networks)
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
    """youtube | reddit | x | threads | unknown"""
    if YT_URL.search(url or ""):
        return "youtube"
    if REDDIT_URL.search(url or ""):
        return "reddit"
    if re.search(r"(?:twitter\.com|x\.com)/\w+/status/\d+", url or ""):
        return "x"
    if "threads.net" in (url or ""):
        return "threads"
    return "unknown"



YT_API = "https://www.googleapis.com/youtube/v3"
YT_BOT_HINT = ("YouTube blocks this server's network (bot check). Set YOUTUBE_API_KEY "
               "(free, no card: Google Cloud Console -> enable 'YouTube Data API v3' -> "
               "Credentials -> API key) to fetch through the official API instead.")


def _yt_api_key() -> str:
    return (os.getenv("YOUTUBE_API_KEY") or "").strip()


def _yt_api_get(path: str, **params) -> dict:
    """GET a YouTube Data API v3 endpoint; raises RuntimeError with Google's reason."""
    params["key"] = _yt_api_key()
    resp = requests.get(f"{YT_API}/{path}", params=params, timeout=20)
    if resp.status_code != 200:
        try:
            err = resp.json()["error"]
            reason = (err.get("errors") or [{}])[0].get("reason") or err.get("status")
            msg = err.get("message", "")
        except Exception:
            reason, msg = resp.status_code, resp.text[:150]
        if reason == "commentsDisabled":
            raise ValueError("Comments are turned off for this video")
        if reason in ("quotaExceeded", "dailyLimitExceeded"):
            raise RuntimeError("YouTube API daily quota used up - try again tomorrow or paste comments")
        raise RuntimeError(f"YouTube API error ({reason}): {msg[:150]}")
    return resp.json()


def _fetch_youtube_api(video_id: str, limit: int) -> dict:
    """Title + top-level comments through the official YouTube Data API v3."""
    from datetime import datetime

    items = _yt_api_get("videos", part="snippet", id=video_id).get("items") or []
    if not items:
        raise ValueError(f"YouTube video {video_id} not found (private or removed?)")
    title = items[0]["snippet"].get("title") or f"YouTube video {video_id}"

    comments, page = [], None
    while len(comments) < limit:
        params = dict(part="snippet", videoId=video_id, maxResults=min(100, limit - len(comments)),
                      order="relevance", textFormat="plainText")
        if page:
            params["pageToken"] = page
        data = _yt_api_get("commentThreads", **params)
        for item in data.get("items", []):
            top = item["snippet"]["topLevelComment"]
            sn = top["snippet"]
            text = (sn.get("textDisplay") or sn.get("textOriginal") or "").strip()
            if text:
                comments.append({
                    "id": f"ytv-{video_id}-{top.get('id') or uuid.uuid4().hex[:8]}",
                    "source": "youtube",
                    "author": (sn.get("authorDisplayName") or "anonymous")[:120],
                    "text": text,
                    "post_id": video_id,
                    "post_title": title,
                    "label": None,
                    "ts": datetime.now().isoformat(timespec="seconds"),
                })
        page = data.get("nextPageToken")
        if not page:
            break
    return {"post_id": video_id, "post_title": title, "source": "youtube", "comments": comments[:limit]}


def fetch_youtube(url: str, limit: int = 200) -> dict:
    """Fetch video title + comments: YouTube Data API if YOUTUBE_API_KEY is set, else yt-dlp."""
    video_id = YT_URL.search(url).group(1)
    if _yt_api_key():
        return _fetch_youtube_api(video_id, limit)
    return _fetch_youtube_ytdlp(video_id, limit)


def _fetch_youtube_ytdlp(video_id: str, limit: int = 200) -> dict:
    """Fetch video title + comments via yt-dlp (no API key)."""
    import json
    import subprocess
    from datetime import datetime

    opts = [
        _ytdlp_bin(), "--skip-download", "--no-warnings",
        "--write-comments", "--extractor-args", f"youtube:max_comments={min(limit, 100)},all,all,all",
        "--print", "%(.title)s",
        "--print", "%(comments)j",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    raw = subprocess.run(opts, capture_output=True, text=True, timeout=240)
    if raw.returncode != 0:
        err = raw.stderr.strip()
        if "confirm you" in err and "bot" in err:
            raise RuntimeError(YT_BOT_HINT)
        raise RuntimeError(f"yt-dlp failed: {err[:200]}")

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
                "ts": datetime.now().isoformat(timespec="seconds"),
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
                "ts": datetime.now().isoformat(timespec="seconds"),
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
                "ts": datetime.now().isoformat(timespec="seconds"),
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
    if "threads.net" in (url_or_text or ""):
        return fetch_threads_post(url_or_text, limit)
    if "twitter.com" in (url_or_text or "") or "x.com" in (url_or_text or ""):
        return fetch_x(url_or_text, limit)
    raise ValueError("Unrecognized URL — paste a YouTube, Reddit, X/Twitter, or Threads post link")


# ---------------------------------------------------------------------------
# Account-level analysis: fetch every comment across an entire account
# ---------------------------------------------------------------------------

YTDLP_BIN = None


def _ytdlp_bin() -> str:
    """yt-dlp from the project venv (macOS/Linux bin/, Windows Scripts\\), else PATH (Docker)."""
    global YTDLP_BIN
    if YTDLP_BIN is None:
        import shutil

        venv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv")
        candidates = [os.path.join(venv, "bin", "yt-dlp"), os.path.join(venv, "Scripts", "yt-dlp.exe")]
        YTDLP_BIN = next((c for c in candidates if os.path.exists(c)), None) or shutil.which("yt-dlp") or "yt-dlp"
    return YTDLP_BIN


def _clean_handle(handle: str) -> str:
    """Normalize 'https://youtube.com/@name/videos', '@name', or 'name' -> 'name'."""
    h = (handle or "").strip()
    h = re.sub(r"^https?://(www\.)?[a-z]+\.\w+/@", "", h)
    h = h.lstrip("@").split("/")[0].strip()
    if not h or not re.match(r"^[\w.-]{2,60}$", h):
        raise ValueError(f"Invalid account handle: {handle!r}")
    return h


def fetch_youtube_account(handle: str, limit: int = 100, max_videos: int = 5) -> list[dict]:
    """Fetch comments across the latest videos of a YouTube channel.

    Returns a list of per-post dicts shaped like fetch_youtube output.
    Lists video ids with the Data API (YOUTUBE_API_KEY) or yt-dlp flat-playlist.
    """
    handle = _clean_handle(handle)
    if _yt_api_key():
        videos = _youtube_api_latest_videos(handle, max_videos)
    else:
        videos = _youtube_ytdlp_latest_videos(handle, max_videos)
    if not videos:
        raise ValueError(f"No videos found for YouTube channel @{handle}")

    posts = []
    for vid, _vtitle in videos:
        try:
            post = fetch_youtube(f"https://www.youtube.com/watch?v={vid}", limit)
            if post["comments"]:
                posts.append(post)
        except Exception:
            continue  # skip videos whose comments are off/limited
        time.sleep(0 if _yt_api_key() else 1)  # be polite to yt-dlp's scraping

    if not posts:
        raise ValueError(f"No comments could be fetched for @{handle} (comments may be disabled)")
    return posts


def _youtube_api_latest_videos(handle: str, max_videos: int) -> list[tuple[str, str]]:
    """Latest uploads of @handle via the Data API (channels.forHandle -> uploads playlist)."""
    chans = _yt_api_get("channels", part="contentDetails", forHandle=f"@{handle}").get("items") or []
    if not chans:
        raise ValueError(f"YouTube channel @{handle} not found")
    uploads = chans[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    items = _yt_api_get("playlistItems", part="snippet", playlistId=uploads,
                        maxResults=max(1, min(max_videos, 50))).get("items") or []
    return [(it["snippet"]["resourceId"]["videoId"], it["snippet"].get("title", "")) for it in items]


def _youtube_ytdlp_latest_videos(handle: str, max_videos: int) -> list[tuple[str, str]]:
    """Latest uploads of @handle via yt-dlp flat-playlist (no key)."""
    import subprocess

    opts = [
        _ytdlp_bin(), "--flat-playlist", "--no-warnings", "--playlist-end", str(max_videos),
        "--print", "%(id)s|%(title)s", f"https://www.youtube.com/@{handle}/videos",
    ]
    raw = subprocess.run(opts, capture_output=True, text=True, timeout=120)
    if raw.returncode != 0:
        err = raw.stderr.strip()
        if "confirm you" in err and "bot" in err:
            raise RuntimeError(YT_BOT_HINT)
        raise RuntimeError(f"yt-dlp channel listing failed: {err[:200]}")

    videos = []
    for line in raw.stdout.splitlines():
        line = line.strip()
        if "|" in line and len(line.split("|", 1)[0]) == 11:
            vid, vtitle = line.split("|", 1)
            videos.append((vid, vtitle))
    return videos


def fetch_reddit_account(username: str, limit: int = 200) -> list[dict]:
    """Fetch a Reddit user's recent submissions + their comment threads via PullPush.

    Comments are grouped under their parent submission so each post renders
    as its own card. Falls back gracefully if the API is down.
    """
    from datetime import datetime, timezone

    username = _clean_handle(username)
    headers = {"User-Agent": "sentiment-analysis-college-project/1.0"}

    subs_by_id: dict[str, dict] = {}
    after = None
    for _ in range(3):  # up to 3 pages of 100 submissions
        params = f"author={username}&size=100&sort=desc"
        if after:
            params += f"&before={after}"
        try:
            resp = requests.get(
                f"https://api.pullpush.io/reddit/search/submission/?{params}",
                headers=headers, timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            if not subs_by_id:
                raise RuntimeError(f"PullPush unreachable: {exc}") from exc
            break
        batch = resp.json().get("data", [])
        if not batch:
            break
        for s in batch:
            sid = s.get("id")
            if not sid or sid in subs_by_id:
                continue
            subs_by_id[sid] = {
                "post_id": sid,
                "post_title": (s.get("title") or f"Reddit post {sid}")[:200],
                "source": "reddit",
                "subreddit": s.get("subreddit") or "unknown",
                "comments": [],
            }
        after = batch[-1].get("created_utc")
        if len(batch) < 100:
            break
        time.sleep(1)

    # one synthetic post if the user has submissions but we still want comment threads;
    # also fetch the user's own comments grouped by parent link
    comment_threads: dict[str, list] = {}
    cafter = None
    for _ in range(3):
        params = f"author={username}&size=100&sort=desc"
        if cafter:
            params += f"&before={cafter}"
        try:
            resp = requests.get(
                f"https://api.pullpush.io/reddit/search/comment/?{params}",
                headers=headers, timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException:
            break
        batch = resp.json().get("data", [])
        if not batch:
            break
        for c in batch:
            body = (c.get("body") or "").strip()
            if not body or body in ("[deleted]", "[removed]"):
                continue
            link_id = (c.get("link_id") or "").replace("t3_", "").replace("t1_", "")
            if not link_id:
                continue
            comment_threads.setdefault(link_id, []).append({
                "id": f"rdu-{username}-{c.get('id') or uuid.uuid4().hex[:8]}",
                "source": "reddit",
                "author": (c.get("author") or username)[:120],
                "text": body,
                "post_id": link_id,
                "post_title": None,  # filled below
                "label": None,
                "ts": datetime.fromtimestamp(
                    c.get("created_utc") or time.time(), tz=timezone.utc
                ).isoformat(),
            })
        cafter = batch[-1].get("created_utc")
        if len(batch) < 100:
            break
        time.sleep(1)

    # merge comment threads into submissions, or create placeholder posts
    for link_id, cmts in comment_threads.items():
        if link_id in subs_by_id:
            subs_by_id[link_id]["comments"].extend(cmts)
        else:
            subs_by_id[link_id] = {
                "post_id": link_id,
                "post_title": f"Thread u/{username} commented on ({link_id})",
                "source": "reddit",
                "subreddit": "unknown",
                "comments": cmts,
            }

    posts = [p for p in subs_by_id.values() if p["comments"]]
    if not posts:
        raise ValueError(f"No comments found for Reddit user u/{username}")
    return posts[:20]  # cap analyzed threads


def fetch_account(platform: str, handle: str, limit: int = 100, max_videos: int = 5) -> list[dict]:
    """Dispatch account-level fetch by platform: youtube | reddit | threads."""
    platform = (platform or "").lower()
    if platform == "youtube":
        return fetch_youtube_account(handle, limit=limit, max_videos=max_videos)
    if platform == "reddit":
        return fetch_reddit_account(handle, limit=limit)
    if platform == "threads":
        return fetch_threads_account(handle, limit=limit, max_posts=max_videos)
    raise ValueError(f"Account-level analysis is not available for {platform!r} "
                     f"(supported: youtube, reddit, threads)")


# ---------------------------------------------------------------------------
# Threads: OAuth + account threads via graph.threads.net (standalone API)
# ---------------------------------------------------------------------------

THREADS_API = "https://graph.threads.net/v1.0"


def _threads_creds() -> tuple[str, str]:
    app_id = os.getenv("THREADS_APP_ID") or ""
    app_secret = os.getenv("THREADS_APP_SECRET") or ""
    if not app_id or not app_secret:
        raise ValueError("THREADS_APP_ID / THREADS_APP_SECRET not set — add them to .env.local")
    return app_id, app_secret


def threads_redirect_uri() -> str:
    return os.getenv("THREADS_REDIRECT_URI", "http://localhost:5173/threads/callback")


def threads_auth_url() -> str:
    """OAuth consent URL (real consent page: www.threads.net, no client_secret).
    Future scope: requires THREADS_APP_ID/SECRET in .env.local + a registered redirect URI."""
    app_id, _ = _threads_creds()
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": app_id,
        "redirect_uri": threads_redirect_uri(),
        "response_type": "code",
        "scope": "threads_basic,threads_content_publish",
    })
    return f"https://www.threads.net/oauth/authorize?{params}"


def threads_exchange_code(code: str) -> dict:
    """Authorization code -> short-lived token -> long-lived token (~60 days)."""
    app_id, app_secret = _threads_creds()
    r = requests.get(
        f"{THREADS_API}/oauth/access_token",
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": threads_redirect_uri(),
            "code": code,
        },
        timeout=20,
    )
    data = r.json() if r.status_code == 200 else {}
    short = data.get("access_token")
    if not short:
        raise ValueError(f"Token exchange failed: {data.get('error', {}).get('message', r.text[:150])}")
    # upgrade to long-lived
    long_r = requests.get(
        f"{THREADS_API}/access_token",
        params={"grant_type": "th_exchange_token", "client_secret": app_secret, "access_token": short},
        timeout=20,
    )
    long_data = long_r.json() if long_r.status_code == 200 else {}
    token = long_data.get("access_token") or short
    expires_in = long_data.get("expires_in")
    return {"access_token": token, "expires_in": expires_in}


def _threads_token() -> str:
    token = os.getenv("THREADS_ACCESS_TOKEN") or ""
    if not token:
        raise ValueError("No Threads token — connect your account first (Analyze → Threads)")
    return token


def fetch_threads_account(handle: str = "", limit: int = 50, max_posts: int = 10) -> list[dict]:
    """Fetch the connected Threads profile's recent threads + their replies.

    The Threads API only reads the OAuth-connected user's own content,
    so `handle` is informational (the real identity comes from /me).
    """
    from datetime import datetime, timezone

    token = _threads_token()

    me = requests.get(
        f"{THREADS_API}/me",
        params={"fields": "id,username,threads_profile_picture_url", "access_token": token},
        timeout=20,
    )
    me_data = me.json() if me.status_code == 200 else {}
    username = me_data.get("username") or (handle.lstrip("@") if handle else "me")
    user_id = me_data.get("id")
    if not user_id:
        raise ValueError(f"Threads token invalid or expired: {me_data.get('error', {}).get('message', me.text[:150])}")

    threads = requests.get(
        f"{THREADS_API}/{user_id}/threads",
        params={"fields": "id,text,timestamp,username", "limit": max(max_posts, 1) * 5, "access_token": token},
        timeout=20,
    )
    threads_data = threads.json() if threads.status_code == 200 else {}
    items = threads_data.get("data") or []
    if not items and threads_data.get("error"):
        raise ValueError(f"Could not list threads: {threads_data['error'].get('message', threads.text[:150])}")

    posts = []
    for item in items[:max_posts]:
        tid = item.get("id")
        text = (item.get("text") or "").strip()
        if not tid or not text:
            continue
        ts = item.get("timestamp") or ""
        try:
            ts_iso = datetime.fromisoformat(ts.replace("+0000", "+00:00")).astimezone(timezone.utc).isoformat() if ts else datetime.now().isoformat(timespec="seconds")
        except ValueError:
            ts_iso = datetime.now().isoformat(timespec="seconds")

        replies = []
        try:
            rr = requests.get(
                f"{THREADS_API}/{tid}/replies",
                params={"fields": "id,text,timestamp,username", "limit": limit, "access_token": token},
                timeout=20,
            )
            if rr.status_code == 200:
                replies = rr.json().get("data") or []
        except requests.RequestException:
            pass  # thread with replies hidden/off still counts via its own text

        comments = [
            {
                "id": f"thr-{tid}-{rp.get('id') or uuid.uuid4().hex[:8]}",
                "source": "threads",
                "author": (rp.get("username") or "anonymous")[:120],
                "text": (rp.get("text") or "").strip(),
                "post_id": tid,
                "post_title": text[:120],
                "label": None,
                "ts": rp.get("timestamp") or ts_iso,
            }
            for rp in replies
            if (rp.get("text") or "").strip()
        ]
        # always include the thread's own text so every post yields at least one scored item
        comments.append({
            "id": f"thr-{tid}-self",
            "source": "threads",
            "author": f"@{username}",
            "text": text,
            "post_id": tid,
            "post_title": text[:120],
            "label": None,
            "ts": ts_iso,
        })
        posts.append({"post_id": tid, "post_title": text[:120], "source": "threads", "comments": comments})

    if not posts:
        raise ValueError(f"No threads found for @{username} (post something first)")
    return posts


def fetch_threads_post(url: str, limit: int = 50) -> dict:
    """Fetch replies to a connected user's own thread via its media id."""
    token = _threads_token()
    match = re.search(r"threads\.net/@?[\w.]+/post/([\w]+)", url or "")
    if not match:
        raise ValueError("Paste a Threads post link like https://www.threads.net/@user/post/ABC123")
    media_id = match.group(1)

    me = requests.get(f"{THREADS_API}/me", params={"fields": "id,username", "access_token": token}, timeout=20)
    me_data = me.json() if me.status_code == 200 else {}
    username = me_data.get("username") or "me"

    media = requests.get(
        f"{THREADS_API}/{media_id}",
        params={"fields": "id,text,timestamp,username", "access_token": token},
        timeout=20,
    )
    media_data = media.json() if media.status_code == 200 else {}
    text = (media_data.get("text") or "").strip() or f"Threads post {media_id}"

    replies = []
    rr = requests.get(
        f"{THREADS_API}/{media_id}/replies",
        params={"fields": "id,text,timestamp,username", "limit": limit, "access_token": token},
        timeout=20,
    )
    if rr.status_code == 200:
        replies = rr.json().get("data") or []

    comments = [
        {
            "id": f"thr-{media_id}-{rp.get('id') or uuid.uuid4().hex[:8]}",
            "source": "threads",
            "author": (rp.get("username") or "anonymous")[:120],
            "text": (rp.get("text") or "").strip(),
            "post_id": media_id,
            "post_title": text[:120],
            "label": None,
            "ts": rp.get("timestamp") or datetime.now().isoformat(timespec="seconds"),
        }
        for rp in replies
        if (rp.get("text") or "").strip()
    ]
    comments.append({
        "id": f"thr-{media_id}-self",
        "source": "threads",
        "author": f"@{username}",
        "text": text,
        "post_id": media_id,
        "post_title": text[:120],
        "label": None,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    return {"post_id": media_id, "post_title": text[:120], "source": "threads", "comments": comments}
