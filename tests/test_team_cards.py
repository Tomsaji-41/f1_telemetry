"""
tests/test_team_cards.py — Unit & Integration tests for Team Cards & Logo Resolution (Phase J)
"""
import pytest
from backend import team_cards, logos

def test_team_cards_endpoint_structure():
    """Verify team cards endpoint contract for a modern season round."""
    data = team_cards.get_team_cards(year=2024, round_num=1)
    assert data.get("status") == "ok"
    assert data.get("year") == 2024
    assert data.get("round") == 1
    cards = data.get("cards", [])
    assert len(cards) >= 10

    # Verify first card structure
    c0 = cards[0]
    assert "constructor_id" in c0 and c0["constructor_id"]
    assert "name" in c0 and c0["name"]
    assert "monogram" in c0 and len(c0["monogram"]) >= 1
    assert "logo" in c0
    assert "championship" in c0
    assert "this_round" in c0
    assert "drivers" in c0
    assert "profile" in c0

def test_team_logo_resolution_and_fallback():
    """Verify that logo resolution returns proxy url for teams with P154, and monogram fallback for others."""
    # McLaren has verified P154 on Wikidata
    mclaren_logo = logos.resolve_team_logo("mclaren", year=2024)
    logo_url = mclaren_logo.get("url") or mclaren_logo.get("logoUrl")
    assert logo_url is not None
    assert "/api/logos/mclaren.png" in logo_url

    # Red Bull has no direct P154 on its racing team entity -> falls back to None with reason
    rb_logo = logos.resolve_team_logo("red_bull", year=2024)
    rb_url = rb_logo.get("url") or rb_logo.get("logoUrl")
    assert rb_url is None
    assert (rb_logo.get("reason") or rb_logo.get("logoReason")) is not None

def test_logo_credits_section():
    """Verify that logo credits array includes licenses and attribution for resolved logos."""
    data = team_cards.get_team_cards(year=2024, round_num=1)
    credits = data.get("logo_credits", [])
    assert len(credits) >= 3
    for cr in credits:
        assert "constructor_id" in cr
        assert "team_name" in cr
        assert "license" in cr
        assert "attribution" in cr
