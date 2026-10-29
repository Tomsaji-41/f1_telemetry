"""
tests/test_chat_matrix.py
Comprehensive 40+ query test matrix validating Pit Boss chat agent:
- Runtime chips
- Context-carrying follow-ups
- Block deduplication
- Deterministic and analytical intent answering
- Honest failure and verified source tagging
"""

import asyncio
import uuid
import pytest
from backend import agent


def run_chat_sync(query: str, last_resolved_race=None, action=None, chip=None, client_id=None):
    """Helper to synchronously run process_chat and collect events with isolated client state."""
    events = []
    c_id = client_id or f"test_{uuid.uuid4().hex[:8]}"

    async def _runner():
        async for ev_type, ev_data in agent.process_chat(
            message=query,
            action=action,
            chip=chip,
            last_resolved_race=last_resolved_race,
            client_id=c_id
        ):
            events.append((ev_type, ev_data))

    asyncio.run(_runner())
    return events


def get_answer_and_done(events):
    answer = next((d for t, d in events if t == "answer"), None)
    clarify = next((d for t, d in events if t == "clarify"), None)
    done = next((d for t, d in events if t == "done"), None)
    return answer, clarify, done


CHAT_QUERIES = [
    # 1-5: Race Winners
    "Who won the 2023 Bahrain Grand Prix?",
    "Who won the 2023 Monza GP?",
    "Winner of Monaco 2022",
    "Who won Silverstone 2021?",
    "Who won the 2020 Abu Dhabi GP?",

    # 6-10: Race Results & Classifications
    "2023 Bahrain GP race results",
    "Spa 2023 race result",
    "Results of the 2022 Australian Grand Prix",
    "Classification for 2021 Dutch GP",
    "2023 Brazilian Grand Prix results",

    # 11-15: Qualifying & Pole Positions
    "Who was on pole at Monza 2023?",
    "Qualifying results Bahrain 2024",
    "Who took pole at Spa 2022?",
    "Qualifying for 2023 Monaco Grand Prix",
    "Pole position Silverstone 2023",

    # 16-20: Standings (Drivers & Constructors)
    "2023 driver championship standings",
    "2023 constructor standings",
    "Driver standings 2022",
    "Constructors championship 2021",
    "F1 standings 2020",

    # 21-25: Pit Stops & Strategy
    "Pit stops Bahrain 2023",
    "How many pit stops at Monza 2022?",
    "Pit stop summary Spa 2023",
    "Tyre stints Bahrain 2023",
    "Tyre stints for Monza 2023",

    # 26-30: Circuit & Venue Information
    "Which circuit hosts the Belgian GP?",
    "Where is the Italian Grand Prix held?",
    "Monza circuit details",
    "Silverstone circuit information",
    "Tell me about the Circuit de Monaco",

    # 31-35: Champions & Historical Records
    "Who won the 2020 F1 championship?",
    "Who is the 2007 world champion?",
    "How many championships does Ferrari have?",
    "Most wins in F1 history",
    "Driver with the most pole positions",

    # 36-40: Driver Profiles & Metrics
    "Lewis Hamilton driver profile",
    "Max Verstappen stats",
    "Fernando Alonso career summary",
    "Charles Leclerc profile",
    "Lando Norris standings",

    # 41-44: Conversational, Greetings & Assistance
    "hello",
    "hi pit boss",
    "help",
    "thank you",
]


@pytest.mark.parametrize("query", CHAT_QUERIES)
def test_chat_matrix_query_response(query):
    events = run_chat_sync(query)
    assert len(events) >= 2, f"Query '{query}' produced insufficient events: {events}"

    answer, clarify, done = get_answer_and_done(events)
    assert (answer is not None or clarify is not None), f"Query '{query}' produced neither answer nor clarify event"
    assert done is not None, f"Query '{query}' produced no done event"

    if answer is not None:
        markdown = answer.get("markdown", "")
        assert isinstance(markdown, str)
        assert len(markdown.strip()) > 0, f"Query '{query}' returned empty markdown"

        # De-duped blocks contract
        blocks = answer.get("blocks", [])
        if blocks:
            seen = set()
            for b in blocks:
                k = (b.get("type"), b.get("id"))
                assert k not in seen, f"Duplicate block key {k} in query '{query}'"
                seen.add(k)
                # Ensure no dead links
                assert "link" not in b
    else:
        # Clarify turn contract
        assert "question" in clarify
        assert isinstance(clarify["question"], str)

    # Done contract
    assert "verified" in done
    assert isinstance(done["verified"], bool)
    assert "timings_ms" in done


def test_context_carrying_followup():
    """Verify context-carrying follow-up: race winner followed by 'and qualifying?'"""
    c_id = f"test_{uuid.uuid4().hex[:8]}"
    # Turn 1: Race result
    events1 = run_chat_sync("Who won Bahrain 2023?", client_id=c_id)
    answer1, _, done1 = get_answer_and_done(events1)
    last_race = done1.get("last_resolved_race")
    assert last_race is not None
    assert last_race.get("year") == 2023

    # Turn 2: Follow-up question without explicit race or year
    events2 = run_chat_sync("what about qualifying?", last_resolved_race=last_race, client_id=c_id)
    ans2, _, done2 = get_answer_and_done(events2)
    assert ans2 is not None
    assert "Bahrain" in ans2.get("markdown") or "Sakhir" in ans2.get("markdown") or "Verstappen" in ans2.get("markdown")
    assert done2.get("verified") is True


def test_runtime_chips_action():
    """Verify clicking a runtime chip carrying intent and slots."""
    chip = {
        "intent": "race_result",
        "slots": {"grand_prix": "monza", "year": 2023}
    }
    events = run_chat_sync("", action="chip", chip=chip)
    ans, _, done = get_answer_and_done(events)
    assert ans is not None
    assert "Monza" in ans.get("markdown") or "Italian" in ans.get("markdown")
    assert done.get("verified") is True

