import pytest
from backend import verifier

def test_verifier_catches_invented_lap_time():
    tool_output = [{"lap_time": "1:32.608", "position": 1, "points": 25.0}]
    
    # Valid answer
    valid_answer = "The fastest lap was 1:32.608 and earned 25.0 points in P1."
    rep_valid = verifier.check(valid_answer, tool_output)
    assert rep_valid["verified"] is True
    assert len(rep_valid["unsupported"]) == 0

    # Invented lap time
    invented_answer = "The driver set a lap time of 1:21.999 which was unexpected."
    rep_invented = verifier.check(invented_answer, tool_output)
    assert rep_invented["verified"] is False
    assert "1:21.999" in rep_invented["unsupported"]

def test_verifier_catches_invented_points_or_numbers():
    tool_output = [{"position": 1, "points": 25.0, "laps": 53}]
    
    # 48.5 points never happened
    answer = "The winner scored 48.5 points over 53 laps."
    rep = verifier.check(answer, tool_output)
    assert rep["verified"] is False
    assert "48.5" in rep["unsupported"]

def test_verifier_ignores_list_numbers_and_follow_up():
    tool_output = [{"winner": "Max Verstappen", "laps": 51}]
    answer = """
1. Max Verstappen won the Grand Prix.
2. The race was 51 laps.

Want to check lap 44 or compare Norris vs Hamilton?
"""
    rep = verifier.check(answer, tool_output)
    assert rep["verified"] is True
    assert len(rep["unsupported"]) == 0
