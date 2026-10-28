import pytest
from backend import resolver

def test_resolve_driver_aliases():
    res = resolver.resolve_driver("VER")
    assert res["status"] == "ok"
    assert res["code"] == "VER"
    assert "Verstappen" in res["name"]

    res_max = resolver.resolve_driver("Max")
    assert res_max["status"] == "ok"
    assert res_max["code"] == "VER"

    res_ham = resolver.resolve_driver("Lewis")
    assert res_ham["status"] == "ok"
    assert "Hamilton" in res_ham["name"]

def test_resolve_driver_ambiguity():
    # Ambiguous Schumacher without specified year
    res = resolver.resolve_driver("Schumacher")
    assert res["status"] == "ambiguous"
    assert len(res["candidates"]) >= 2

def test_resolve_gp_known_tracks():
    # 2023 Monza is Italian GP
    res_monza = resolver.resolve_gp("Monza", 2023)
    assert res_monza["status"] == "ok"
    assert "Italian" in res_monza["grand_prix"]

    # 2024 Spa is Belgian GP
    res_spa = resolver.resolve_gp("Spa", 2024)
    assert res_spa["status"] == "ok"
    assert "Belgian" in res_spa["grand_prix"]

    # Silverstone is British GP
    res_silverstone = resolver.resolve_gp("Silverstone", 2024)
    assert res_silverstone["status"] == "ok"
    assert "British" in res_silverstone["grand_prix"]

def test_resolve_team_aliases():
    assert resolver.resolve_team("Scuderia")["status"] == "ok"
    assert resolver.resolve_team("Ferrari")["status"] == "ok"
    assert resolver.resolve_team("Brawn")["status"] == "ok"
    assert resolver.resolve_team("AlphaTauri")["status"] == "ok"
    assert resolver.resolve_team("Racing Bulls")["status"] == "ok"
    assert resolver.resolve_team("Alpine")["status"] == "ok"
