import pytest
import asyncio
from unittest.mock import patch, MagicMock
from backend import agent, tools, resolver

def run_async(coro):
    return asyncio.run(coro)

def test_hello_no_tool_calls_no_sources():
    """Rule 8: 'hello' must not trigger tool calls and must have sources=[] and verified=True."""
    async def _test():
        with patch("backend.tools.get_race_result") as mock_tool:
            events = []
            async for ev_type, ev_data in agent.process_chat(message="hello"):
                events.append((ev_type, ev_data))

            assert mock_tool.call_count == 0
            done_ev = next(d for t, d in events if t == "done")
            assert done_ev.get("sources") == []
            assert done_ev.get("verified") is True
            ans_ev = next(d for t, d in events if t == "answer")
            assert "Welcome to **Pit Boss**" in ans_ev.get("markdown")

    run_async(_test())

def test_tool_failure_propagates_verified_false():
    """Rule 1: If any tool returns status != 'ok', verified must be False, sources must be empty."""
    async def _test():
        with patch("backend.tools.get_race_result", return_value={"status": "not_available", "reason": "No data found for test GP", "source": "Jolpica"}):
            events = []
            async for ev_type, ev_data in agent.process_chat(message="Who won the test GP 2023?"):
                events.append((ev_type, ev_data))

            done_ev = next(d for t, d in events if t == "done")
            assert done_ev.get("verified") is False
            assert done_ev.get("sources") == []
            ans_ev = next(d for t, d in events if t == "answer")
            assert "could not be retrieved" in ans_ev.get("markdown") or "No race results" in ans_ev.get("markdown")

    run_async(_test())

def test_no_round_1_default_on_standings():
    """Rule 3: Standings query must never set last_race / round 1 default in context."""
    async def _test():
        with patch("backend.tools.get_standings", return_value={"status": "ok", "standings": [], "round": 18, "total_rounds": 24}):
            events = []
            async for ev_type, ev_data in agent.process_chat(message="standings 2023"):
                events.append((ev_type, ev_data))

            done_ev = next(d for t, d in events if t == "done")
            assert done_ev.get("last_resolved_race") is None or done_ev.get("last_resolved_race") == {}

    run_async(_test())

def test_circuit_lookup_failure_message():
    """Rule 2 & 8: 'Which circuit hosts Belgian GP?' with no data must show failure message, not hollow template."""
    async def _test():
        with patch("backend.tools.get_circuit_info", return_value={"status": "not_available", "reason": "Circuit lookup simulated outage", "source": "Jolpica"}):
            events = []
            async for ev_type, ev_data in agent.process_chat(message="Which circuit hosts the Belgian GP?"):
                events.append((ev_type, ev_data))

            done_ev = next(d for t, d in events if t == "done")
            assert done_ev.get("verified") is False
            assert done_ev.get("sources") == []
            ans_ev = next(d for t, d in events if t == "answer")
            md = ans_ev.get("markdown")
            assert "The circuit is located." not in md
            assert "could not be retrieved from Jolpica" in md or "Circuit lookup simulated outage" in md

    run_async(_test())
