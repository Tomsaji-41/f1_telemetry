import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import driver_cards

client = TestClient(app)

def test_driver_cards_structure():
    # Test 2024 Round 1 (Bahrain GP)
    cards_res = driver_cards.get_driver_cards(2024, 1)
    assert cards_res["status"] == "ok"
    assert cards_res["year"] == 2024
    assert cards_res["round"] == 1
    cards = cards_res["cards"]
    assert len(cards) >= 18, f"Expected at least 18 active drivers, got {len(cards)}"

    # Check top driver (Max Verstappen won 2024 R1)
    winner_card = cards[0]
    assert winner_card["round_stats"]["finish_position"] == 1
    assert "VER" in winner_card["identity"]["code"]

    # Verify all expected sections in the card contract
    for c in cards[:5]:
        assert "identity" in c
        assert "code" in c["identity"]
        assert "team_color" in c["identity"]
        assert "round_stats" in c
        assert "finish_position" in c["round_stats"]
        assert "season_stats" in c
        assert "recent_form" in c
        assert isinstance(c["recent_form"], list)
        assert "teammate_comparison" in c
        assert "career_highlights" in c
        assert "total_wins" in c["career_highlights"]

def test_api_drivers_cards_endpoint():
    res = client.get("/api/drivers/cards?year=2024&round=1")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "cards" in data
    assert len(data["cards"]) > 0

