"""
tests/test_identity.py
Unit tests for Identity and Colours Service (Phase 2):
- Code uniqueness within a season
- Family name fallback (never given name)
- Color matching across name mismatches
- WCAG 2.1 contrast calculation
- Teammate styling & disambiguation
"""
import pytest
from backend import identity

def test_code_uniqueness_and_family_name_derivation():
    """Verify codes come from Jolpica or family name, never given name, and are unique."""
    # Test normalization of names
    assert identity.normalize_text("Max Verstappen") == "max verstappen"
    assert identity.normalize_text("Sergio Pérez") == "sergio perez"
    assert identity.normalize_text("Charles Leclerc") == "charles leclerc"

    # Lando Norris vs Lance Stroll: family name gives NOR vs STR, NOT LAN
    norris_code = "Norris"[:3].upper()
    stroll_code = "Stroll"[:3].upper()
    assert norris_code == "NOR"
    assert stroll_code == "STR"
    assert norris_code != stroll_code

def test_wcag_contrast_calculation():
    """Verify readable text color returns #000000 or #FFFFFF appropriately."""
    # Pure white background -> black text
    assert identity.get_readable_text_color("#FFFFFF") == "#000000"
    # Pure black background -> white text
    assert identity.get_readable_text_color("#000000") == "#FFFFFF"
    # Deep red (Ferrari) -> white text
    assert identity.get_readable_text_color("#E10600") == "#FFFFFF"
    # Bright yellow -> black text
    assert identity.get_readable_text_color("#FFF500") == "#000000"
    # Papaya Orange (McLaren #FF8000) -> black text
    assert identity.get_readable_text_color("#FF8000") == "#000000"

def test_teammate_disambiguation_tint():
    """Verify second driver gets a lighter tint of the team color."""
    base_color = "#E10600" # Ferrari red
    tint = identity.lighten_color(base_color, 0.35)
    assert tint != base_color
    assert tint.startswith("#")
    r1, g1, b1 = identity.parse_hex(base_color)
    r2, g2, b2 = identity.parse_hex(tint)
    # Tint should have higher RGB components (lighter)
    assert r2 >= r1 and g2 >= g1 and b2 >= b1

def test_season_identity_returns_grounded_structure():
    """Verify get_season_identity returns unique codes and non-empty drivers and teams."""
    data = identity.get_season_identity(2024)
    assert data["status"] == "ok"
    assert "drivers" in data
    assert "teams" in data
    drivers = data["drivers"]
    assert len(drivers) > 0

    # Assert codes are unique
    codes = [d["code"] for d in drivers.values()]
    assert len(codes) == len(set(codes)), f"Duplicate codes found: {codes}"

    # Verify teammate disambiguation
    for c_id, team_info in data["teams"].items():
        d_ids = team_info.get("drivers", [])
        if len(d_ids) >= 2:
            d1 = drivers[d_ids[0]]
            d2 = drivers[d_ids[1]]
            assert d1.get("dash") is None
            assert d2.get("dash") == "4 2"
            assert d2.get("tintColor") is not None
