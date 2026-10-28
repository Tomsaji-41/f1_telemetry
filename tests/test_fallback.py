import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend import config, llm_router, verifier

@pytest.fixture(autouse=True)
def reset_breaker():
    llm_router.reset_circuit_breaker()
    yield
    llm_router.reset_circuit_breaker()

class MockChunk:
    def __init__(self, text):
        self.text = text

class MockDelta:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.delta = MockDelta(content)

class MockGroqEvent:
    def __init__(self, content):
        self.choices = [MockChoice(content)]

def test_1_gemini_sleeps_hedged_by_groq(monkeypatch):
    """1. Gemini sleeps 6 s before the first token -> Groq answer is used, fallback_reason 'timeout', total time under 5 s."""
    async def run_test():
        # Mock Gemini to sleep 6s before first token
        async def slow_gemini_stream(*args, **kwargs):
            await asyncio.sleep(6.0)
            yield MockChunk("Gemini late chunk")

        mock_gem_client = MagicMock()
        mock_gem_client.aio.models.generate_content_stream = MagicMock(return_value=slow_gemini_stream())

        # Mock Groq to answer quickly
        async def fast_groq_stream(*args, **kwargs):
            await asyncio.sleep(0.05)
            yield MockGroqEvent("Groq fast answer")

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(return_value=fast_groq_stream())

        monkeypatch.setattr(llm_router, "gem", mock_gem_client)
        monkeypatch.setattr(llm_router, "groq", mock_groq_client)

        t0 = time.time()
        res = await llm_router.generate_response("System prompt", "User prompt")
        duration = time.time() - t0

        assert res["model"] == "groq"
        assert res["fallback_reason"] == "timeout"
        assert "Groq fast answer" in res["text"]
        assert duration < 5.0, f"Expected total time under 5s, took {duration:.2f}s"

    asyncio.run(run_test())

def test_2_gemini_raises_429_uses_groq(monkeypatch):
    """2. Gemini raises a 429 -> Groq is used, fallback_reason 'rate_limit'."""
    async def run_test():
        async def error_gemini_stream(*args, **kwargs):
            raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded")
            yield MockChunk("Never reached")

        mock_gem_client = MagicMock()
        mock_gem_client.aio.models.generate_content_stream = MagicMock(return_value=error_gemini_stream())

        async def fast_groq_stream(*args, **kwargs):
            yield MockGroqEvent("Groq handled 429 fallback")

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(return_value=fast_groq_stream())

        monkeypatch.setattr(llm_router, "gem", mock_gem_client)
        monkeypatch.setattr(llm_router, "groq", mock_groq_client)

        res = await llm_router.generate_response("System prompt", "User prompt")
        assert res["model"] == "groq"
        assert res["fallback_reason"] == "rate_limit"
        assert "Groq handled 429 fallback" in res["text"]

    asyncio.run(run_test())

def test_3_circuit_breaker_trips_after_two_failures(monkeypatch):
    """3. Two Gemini failures in 60 s -> the third request goes straight to Groq without waiting."""
    async def run_test():
        gemini_call_count = 0

        async def failing_gemini_stream(*args, **kwargs):
            nonlocal gemini_call_count
            gemini_call_count += 1
            raise RuntimeError("500 Internal Server Error")
            yield MockChunk("Never reached")

        mock_gem_client = MagicMock()
        mock_gem_client.aio.models.generate_content_stream = MagicMock(side_effect=lambda *a, **kw: failing_gemini_stream())

        async def groq_stream(*args, **kwargs):
            yield MockGroqEvent("Groq response")

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(side_effect=lambda *a, **kw: groq_stream())

        monkeypatch.setattr(llm_router, "gem", mock_gem_client)
        monkeypatch.setattr(llm_router, "groq", mock_groq_client)

        # Request 1: fails
        res1 = await llm_router.generate_response("System", "Q1")
        assert res1["model"] == "groq"
        assert gemini_call_count == 1

        # Request 2: fails -> trips circuit breaker
        res2 = await llm_router.generate_response("System", "Q2")
        assert res2["model"] == "groq"
        assert gemini_call_count == 2
        assert llm_router._gemini_blocked() is True

        # Request 3: goes straight to Groq without calling Gemini
        t0 = time.time()
        res3 = await llm_router.generate_response("System", "Q3")
        duration = time.time() - t0

        assert res3["model"] == "groq"
        # Gemini call count should NOT have increased
        assert gemini_call_count == 2
        assert duration < 0.5, f"Expected fast route directly to Groq, took {duration:.2f}s"

    asyncio.run(run_test())

def test_4_both_fail_returns_fast_path_table(monkeypatch):
    """4. Both fail -> the fast-path table is returned with the 'service is busy' line."""
    async def run_test():
        async def error_gemini_stream(*args, **kwargs):
            raise RuntimeError("Gemini down")
            yield MockChunk("")

        async def error_groq_stream(*args, **kwargs):
            raise RuntimeError("Groq down")
            yield MockGroqEvent("")

        mock_gem_client = MagicMock()
        mock_gem_client.aio.models.generate_content_stream = MagicMock(return_value=error_gemini_stream())

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock(return_value=error_groq_stream())

        monkeypatch.setattr(llm_router, "gem", mock_gem_client)
        monkeypatch.setattr(llm_router, "groq", mock_groq_client)

        sample_data = [
            {"position": 1, "driver": "VER", "team": "Red Bull", "points": 25},
            {"position": 2, "driver": "NOR", "team": "McLaren", "points": 18}
        ]

        res = await llm_router.generate_response("System", "User", tool_data=sample_data)
        assert res["text"], "Must never return an empty reply"
        assert "The analysis service is busy, showing the data only." in res["text"]
        assert "VER" in res["text"]
        assert "Red Bull" in res["text"]

    asyncio.run(run_test())

def test_5_gemini_answers_quickly_groq_never_called(monkeypatch):
    """5. Gemini answers quickly -> Groq is never called (assert call count 0)."""
    async def run_test():
        async def fast_gemini_stream(*args, **kwargs):
            yield MockChunk("Quick Gemini answer")

        mock_gem_client = MagicMock()
        mock_gem_client.aio.models.generate_content_stream = MagicMock(return_value=fast_gemini_stream())

        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create = AsyncMock()

        monkeypatch.setattr(llm_router, "gem", mock_gem_client)
        monkeypatch.setattr(llm_router, "groq", mock_groq_client)

        res = await llm_router.generate_response("System", "User")
        assert res["model"] == "gemini"
        assert res["fallback_reason"] is None
        assert "Quick Gemini answer" in res["text"]
        assert mock_groq_client.chat.completions.create.call_count == 0

    asyncio.run(run_test())

def test_6_groq_invented_cause_cleaned_by_verifier():
    """6. Groq output containing an invented cause ('probably traffic') is cleaned by the verifier exactly like Gemini output."""
    groq_output = "Norris dropped 1.8 seconds on lap 31, probably traffic in sector 2."
    gemini_output = "Norris dropped 1.8 seconds on lap 31, probably traffic in sector 2."

    tool_outputs = [{"lap": 31, "driver": "NOR", "delta": 1.8}]  # No traffic mentioned

    cleaned_groq = verifier.clean(groq_output, tool_outputs)
    cleaned_gemini = verifier.clean(gemini_output, tool_outputs)

    assert "probably traffic" not in cleaned_groq
    assert "probably traffic" not in cleaned_gemini
    assert cleaned_groq == cleaned_gemini

    # Verify check() also catches and cleans it
    check_rep = verifier.check(groq_output, tool_outputs)
    assert "probably traffic" in check_rep["unsupported_causes"]
    assert "probably traffic" not in check_rep["cleaned_text"]

def test_7_grep_test_no_api_keys_in_repo():
    """7. Grep test: no string starting with 'gsk_' or 'AIza' exists anywhere in the repo."""
    repo_root = Path(__file__).resolve().parent.parent

    # .env must be in .gitignore
    gitignore_path = repo_root / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist"
    gitignore_content = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in gitignore_content, ".env must be in .gitignore"

    # Directories and files to ignore during repo grep
    ignored_patterns = {
        ".git", ".venv", "__pycache__", ".pytest_cache", "node_modules",
        "cache", "f1_cache", ".env", ".env.local"
    }

    # Use dynamically constructed prefix tokens to avoid matching this test file
    forbidden_prefixes = ("g" + "sk_", "A" + "Iza")
    found_violations = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        parts = set(path.parts)
        if any(ignored in parts for ignored in ignored_patterns):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                # Check for actual key occurrences
                for token in line.split():
                    clean_token = token.strip("\"'`;,(){}[]")
                    for prefix in forbidden_prefixes:
                        if clean_token.startswith(prefix) and len(clean_token) > len(prefix):
                            found_violations.append(f"{path.relative_to(repo_root)}: {clean_token[:8]}...")
        except Exception:
            pass

    assert len(found_violations) == 0, f"Found API key prefix violations in files: {found_violations}"
