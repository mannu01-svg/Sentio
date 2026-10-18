"""Tests for Threads fetchers + OAuth helpers (mocked, no network)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fetcher"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetchers  # noqa: E402


def test_detect_platform_threads():
    assert fetchers.detect_platform("https://www.threads.net/@user/post/CxAbc123") == "threads"
    assert fetchers.detect_platform("https://youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"


def test_threads_auth_url_shape(monkeypatch):
    monkeypatch.setenv("THREADS_APP_ID", "12345")
    monkeypatch.setenv("THREADS_APP_SECRET", "deadbeef")
    url = fetchers.threads_auth_url()
    assert url.startswith("https://www.threads.net/oauth/authorize?")
    assert "client_id=12345" in url
    assert "client_secret" not in url  # real consent page takes no secret
    assert "threads_basic" in url
    assert "localhost%3A5173%2Fthreads%2Fcallback" in url


def test_threads_creds_missing(monkeypatch):
    monkeypatch.delenv("THREADS_APP_ID", raising=False)
    monkeypatch.delenv("THREADS_APP_SECRET", raising=False)
    try:
        fetchers._threads_creds()
        assert False, "should raise"
    except ValueError as exc:
        assert "THREADS_APP_ID" in str(exc)


def test_fetch_threads_account(monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "test-token")

    class FakeResp:
        def __init__(self, data):
            self._data = data
            self.status_code = 200
            self.text = "{}"
        def json(self):
            return self._data

    def fake_get(url, params=None, timeout=None):
        if "/me" in url:
            return FakeResp({"id": "999", "username": "tester"})
        if "/threads" in url:
            return FakeResp({"data": [{"id": "t1", "text": "hello world", "timestamp": "2026-01-01T00:00:00+0000"}]})
        if "/replies" in url:
            return FakeResp({"data": [{"id": "r1", "text": "nice post", "username": "fan", "timestamp": "2026-01-01T01:00:00+0000"}]})
        return FakeResp({})

    monkeypatch.setattr("requests.get", fake_get)
    posts = fetchers.fetch_threads_account("tester")
    assert len(posts) == 1
    post = posts[0]
    assert post["source"] == "threads"
    assert post["post_id"] == "t1"
    texts = [c["text"] for c in post["comments"]]
    assert "nice post" in texts and "hello world" in texts  # replies + own thread text
    assert all(c["id"].startswith("thr-t1-") for c in post["comments"])


def test_fetch_threads_account_requires_token(monkeypatch):
    monkeypatch.delenv("THREADS_ACCESS_TOKEN", raising=False)
    try:
        fetchers.fetch_threads_account("x")
        assert False, "should raise"
    except ValueError as exc:
        assert "token" in str(exc).lower()


def test_fetch_account_dispatcher_threads(monkeypatch):
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "tok")
    called = {}
    monkeypatch.setattr(fetchers, "fetch_threads_account", lambda h, **kw: called.setdefault("hit", h) or [])
    fetchers.fetch_account("threads", "tester")
    assert called.get("hit") == "tester"


def test_fetch_account_dispatcher_unknown():
    try:
        fetchers.fetch_account("myspace", "tom")
        assert False, "should raise"
    except ValueError as exc:
        assert "myspace" in str(exc)


def test_persist_env_roundtrip(tmp_path, monkeypatch):
    import api.main as api_main
    env_file = tmp_path / ".env.local"
    env_file.write_text("# comment\nEXISTING=1\n")

    real_open = open

    def fake_open(path, *a, **kw):
        if ".env.local" in str(path):
            return real_open(env_file, *a, **kw)
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", fake_open)
    api_main._persist_env("NEW_KEY", "val1")
    content = env_file.read_text()
    assert "NEW_KEY=val1" in content
    api_main._persist_env("NEW_KEY", "val2")
    content = env_file.read_text()
    assert "NEW_KEY=val2" in content and "val1" not in content
    assert "EXISTING=1" in content and "# comment" in content
