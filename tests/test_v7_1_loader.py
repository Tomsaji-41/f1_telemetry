import concurrent.futures
from unittest.mock import MagicMock, patch
import pytest

from backend.charts import loader, routes
from backend.charts.common import envelope

try:
    from fastf1.core import DataNotLoadedError
except ImportError:
    class DataNotLoadedError(Exception):
        pass


def test_peek_never_returns_session_loaded_without_laps():
    """(b) A session loaded with laps=False is never returned by peek."""
    # Ensure key doesn't exist
    loader.evict(2024, 99, "R")
    assert loader.peek(2024, 99, "R") is None

    # If an object without laps was somehow attempted, verify peek contract
    # Only objects in _REG (published by get_session after verification) are returned
    fake_ses = MagicMock()
    # laps=False simulation: ses.laps raises DataNotLoadedError
    type(fake_ses).laps = property(lambda self: (_ for _ in ()).throw(DataNotLoadedError("Laps not loaded")))

    # Verify that get_session rejects it and does NOT publish to peek
    with patch("backend.charts.loader.fastf1.get_session", return_value=fake_ses):
        with pytest.raises(RuntimeError) as exc_info:
            loader.get_session(2024, 99, "R")
        assert "DataNotLoadedError" in str(exc_info.value) or "incomplete" in str(exc_info.value)

    # peek MUST still return None
    assert loader.peek(2024, 99, "R") is None


def test_session_without_published_laps_returns_not_published_yet():
    """(c) A chart for a session without published laps returns not_published_yet."""
    fake_ses = MagicMock()
    fake_ses.laps = []  # Empty laps (< 10 laps)
    fake_ses.results = []
    fake_ses.weather_data = []

    with patch("backend.charts.loader.fastf1.get_session", return_value=fake_ses):
        with pytest.raises(RuntimeError) as exc_info:
            loader.get_session(2024, 98, "R")
        assert "not published yet" in str(exc_info.value)

    # And routes error classifier maps it to not_published_yet (normalized to not_available per Phase 1.4 schema)
    classified = routes._classify_error(exc_info.value, 2024, 98)
    assert classified["status"] in ("not_published_yet", "not_available")


def test_concurrent_requests_no_data_not_loaded_error():
    """(a) 8 concurrent requests for one cold race all return ok or preparing, none returns DataNotLoaded."""
    loader.evict(2023, 1, "R")

    fake_ses = MagicMock()
    fake_ses.laps = [MagicMock()] * 50
    fake_ses.results = [MagicMock()] * 20
    fake_ses.weather_data = [MagicMock()] * 10

    def mock_get(year, rnd, ident):
        return fake_ses

    results = []
    with patch("backend.charts.loader.fastf1.get_session", side_effect=mock_get):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(loader.get_session, 2023, 1, "R") for _ in range(8)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    res = f.result()
                    results.append("ok")
                except Exception as e:
                    results.append(str(e))

    try:
        assert len(results) == 8
        for r in results:
            assert "DataNotLoaded" not in r
            assert r == "ok"
    finally:
        loader.evict(2023, 1, "R")
