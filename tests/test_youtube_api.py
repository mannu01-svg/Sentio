"""YouTube fetching: official Data API when YOUTUBE_API_KEY is set, yt-dlp otherwise.

Network calls are mocked - no key or internet needed.
"""
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fetcher"))
import fetchers  # noqa: E402

VID = "dQw4w9WgXcQ"


class FakeResp:
    def __init__(self, status, payload):
        self.status_code, self._payload, self.text = status, payload, str(payload)

    def json(self):
        return self._payload


def _comment(i):
    return {"snippet": {"topLevelComment": {"id": f"c{i}", "snippet": {
        "textDisplay": f"comment number {i}", "authorDisplayName": f"@viewer{i}"}}}}


def test_uses_data_api_when_key_set(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url.rsplit("/", 1)[-1], dict(params)))
        if url.endswith("/videos"):
            return FakeResp(200, {"items": [{"snippet": {"title": "DBMS Lecture"}}]})
        if "pageToken" not in params:
            return FakeResp(200, {"items": [_comment(i) for i in range(3)], "nextPageToken": "p2"})
        return FakeResp(200, {"items": [_comment(i) for i in range(3, 5)]})

    monkeypatch.setattr(fetchers.requests, "get", fake_get)
    monkeypatch.setattr(fetchers.subprocess if hasattr(fetchers, "subprocess") else subprocess, "run",
                        lambda *a, **k: pytest.fail("yt-dlp must not run when a key is set"))

    out = fetchers.fetch(f"https://www.youtube.com/watch?v={VID}", limit=10)
    assert out["post_title"] == "DBMS Lecture"
    assert [c["text"] for c in out["comments"]] == [f"comment number {i}" for i in range(5)]
    assert out["comments"][0]["id"] == f"ytv-{VID}-c0"
    assert all(p["key"] == "test-key" for _, p in calls)
    assert [name for name, _ in calls] == ["videos", "commentThreads", "commentThreads"]


def test_respects_limit(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/videos"):
            return FakeResp(200, {"items": [{"snippet": {"title": "T"}}]})
        return FakeResp(200, {"items": [_comment(i) for i in range(params["maxResults"])], "nextPageToken": "x"})

    monkeypatch.setattr(fetchers.requests, "get", fake_get)
    assert len(fetchers.fetch_youtube(f"https://youtu.be/{VID}", limit=7)["comments"]) == 7


def test_comments_disabled_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")

    def fake_get(url, params=None, timeout=None):
        if url.endswith("/videos"):
            return FakeResp(200, {"items": [{"snippet": {"title": "T"}}]})
        return FakeResp(403, {"error": {"message": "disabled", "errors": [{"reason": "commentsDisabled"}]}})

    monkeypatch.setattr(fetchers.requests, "get", fake_get)
    with pytest.raises(ValueError, match="Comments are turned off"):
        fetchers.fetch_youtube(f"https://youtu.be/{VID}")


def test_bot_check_without_key_explains_the_fix(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    class Done:
        returncode, stdout = 1, ""
        stderr = "ERROR: [youtube] x: Sign in to confirm you’re not a bot. Use --cookies"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(RuntimeError, match="YOUTUBE_API_KEY"):
        fetchers.fetch_youtube(f"https://youtu.be/{VID}")


def test_channel_listing_via_api(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")

    def fake_get(url, params=None, timeout=None):
        name = url.rsplit("/", 1)[-1]
        if name == "channels":
            assert params["forHandle"] == "@gatesmashers"
            return FakeResp(200, {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if name == "playlistItems":
            return FakeResp(200, {"items": [{"snippet": {"title": "Ep1", "resourceId": {"videoId": VID}}}]})
        if name == "videos":
            return FakeResp(200, {"items": [{"snippet": {"title": "Ep1"}}]})
        return FakeResp(200, {"items": [_comment(1)]})

    monkeypatch.setattr(fetchers.requests, "get", fake_get)
    posts = fetchers.fetch_youtube_account("https://youtube.com/@gatesmashers", limit=5, max_videos=3)
    assert len(posts) == 1 and posts[0]["post_title"] == "Ep1"
