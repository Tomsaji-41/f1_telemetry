import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_routes_not_404():
    """Verify all expected routes exist and do not return 404."""
    routes_to_check = [
        ("GET", "/", None),
        ("GET", "/docs", None),
        ("GET", "/api/health", None),
        ("GET", "/api/live", None),
        ("GET", "/api/conversations", {"X-Client-Id": "test-client"}),
        ("GET", "/api/metrics", None),
        ("POST", "/api/conversations", {"X-Client-Id": "test-client"}),
        ("GET", "/api/v1/facts/2024/1", None),
        ("GET", "/api/v1/race/2024/1", None),
        ("GET", "/api/v1/telemetry/2024/1/VER/HAM", None),
    ]

    for method, path, headers in routes_to_check:
        h = headers or {}
        if method == "GET":
            resp = client.get(path, headers=h)
        elif method == "POST":
            payload = {"title": "Test Thread"} if path == "/api/conversations" else {"text": "Clean this"}
            resp = client.post(path, json=payload, headers=h)
        assert resp.status_code != 404, f"Route {method} {path} returned 404!"


def test_conversations_flow():
    """Test saving and retrieving conversations with X-Client-Id header."""
    headers = {"X-Client-Id": "unit-test-client"}
    post_resp = client.post(
        "/api/conversations",
        headers=headers,
        json={"title": "Monza Strategy Chat", "messages": [{"role": "user", "content": "monza 2023"}]}
    )
    assert post_resp.status_code == 200
    data = post_resp.json()
    assert data.get("status") == "ok"
    assert data.get("conversation", {}).get("title") == "Monza Strategy Chat"

    get_resp = client.get("/api/conversations", headers=headers)
    assert get_resp.status_code == 200
    convs = get_resp.json().get("conversations", [])
    assert len(convs) >= 1
    assert convs[0].get("title") == "Monza Strategy Chat"


def test_chat_stream_monza():
    """Smoke test: sends 'monza 2023' and expects SSE stream with answer or clarify event."""
    resp = client.post("/api/chat/stream", json={"message": "monza 2023"})
    assert resp.status_code == 200
    content = resp.text
    assert ("event: answer" in content) or ("event: clarify" in content), f"Expected answer or clarify event in SSE output: {content}"
    assert "event: done" in content


def test_chat_stream_verstappen_strategy_clarify():
    """Test: sends 'verstappen race strategy' and expects clarify event asking for season."""
    resp = client.post("/api/chat/stream", json={"message": "verstappen race strategy"})
    assert resp.status_code == 200
    content = resp.text
    assert "event: clarify" in content
    assert "season" in content.lower() or "year" in content.lower()


def test_dead_chat_route_is_removed():
    """Unsupported /api/chat request returns 422 (or 404/405)."""
    resp = client.post("/api/chat", json={"message": "test"})
    assert resp.status_code in (404, 405, 422)
