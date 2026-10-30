"""
tests/test_logos.py — Tests for team logo resolution, HTTP layer, override priority, and cache hygiene.
"""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend import logos, cache


def test_override_directory_takes_priority(tmp_path):
    """Verify user-supplied logo in LOGO_OVERRIDE_DIR takes priority over runtime resolution."""
    override_file = tmp_path / "ferrari.png"
    override_file.write_bytes(b"\x89PNG\r\n\x1a\nFakeFerrariLogoData")

    with patch.dict(os.environ, {"LOGO_OVERRIDE_DIR": str(tmp_path)}):
        # Re-evaluate override dir
        with patch.object(logos, "OVERRIDE_DIR", tmp_path):
            res = logos.resolve_team_logo("ferrari", year=2024)
            assert res["logoSource"] == "local_override"
            assert res["logoUrl"] == "/api/logos/ferrari.png?year=2024"

            # Verify bytes getter returns the override file
            bytes_data, mime = logos.get_logo_image_bytes("ferrari", year=2024)
            assert bytes_data == b"\x89PNG\r\n\x1a\nFakeFerrariLogoData"
            assert mime == "image/png"


def test_multiple_p154_values_prefers_no_end_date_and_preferred_rank():
    """Verify claim selection prefers preferred rank and claims without an end time qualifier (P582)."""
    qid = "Q_TEST_TEAM"
    mock_entity_data = {
        "entities": {
            qid: {
                "claims": {
                    "P154": [
                        {
                            "rank": "normal",
                            "mainsnak": {"datavalue": {"value": "OldLogo_1990.png"}},
                            "qualifiers": {
                                "P580": [{"datavalue": {"value": {"time": "+1990-01-01T00:00:00Z"}}}],
                                "P582": [{"datavalue": {"value": {"time": "+1999-12-31T00:00:00Z"}}}]
                            }
                        },
                        {
                            "rank": "normal",
                            "mainsnak": {"datavalue": {"value": "CurrentStandardLogo.png"}},
                            "qualifiers": {
                                "P580": [{"datavalue": {"value": {"time": "+2020-01-01T00:00:00Z"}}}]
                                # No P582 (no end date)
                            }
                        },
                        {
                            "rank": "preferred",
                            "mainsnak": {"datavalue": {"value": "PreferredCurrentLogo.svg"}},
                            "qualifiers": {
                                "P580": [{"datavalue": {"value": {"time": "+2022-01-01T00:00:00Z"}}}]
                            }
                        }
                    ]
                }
            }
        }
    }

    with patch("backend.logos._http_get_json", return_value=mock_entity_data):
        file, resolved_qid, note = logos._extract_p154_filename(qid)
        # Should pick the preferred rank one
        assert file == "PreferredCurrentLogo.svg"
        assert resolved_qid == qid


def test_wikipedia_redirect_and_disambiguation_handling():
    """Verify Wikipedia redirects are followed and disambiguation pages fallback gracefully."""
    mock_wp_disambig = {
        "query": {
            "pages": {
                "123": {
                    "pageid": 123,
                    "title": "Disambiguation Page",
                    "pageprops": {
                        "disambiguation": "",
                        "wikibase_item": "Q_DISAMBIG"
                    }
                }
            }
        }
    }
    with patch("backend.logos._http_get_json", return_value=mock_wp_disambig), \
         patch("backend.logos._search_wikidata_f1_team", return_value="Q_FOUND_TEAM"):
        qid = logos._get_wikidata_qid_from_wikipedia("Test Team Page", team_name="Test Team")
        assert qid == "Q_FOUND_TEAM"


def test_svg_thumbnail_path_via_commons_imageinfo():
    """Verify Commons imageinfo API is queried with iiurlwidth to request PNG rasterization rather than raw SVG."""
    captured_urls = []

    def mock_http(url, *args, **kwargs):
        captured_urls.append(url)
        if "commons.wikimedia.org" in url:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "imageinfo": [{
                                "thumburl": "https://upload.wikimedia.org/thumb/logo.svg/400px-logo.svg.png",
                                "url": "https://upload.wikimedia.org/logo.svg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:logo.svg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "Artist": {"value": "John Doe"}
                                }
                            }]
                        }
                    }
                }
            }
        if "Special:EntityData" in url:
            return {
                "entities": {
                    "Q172030": {
                        "claims": {
                            "P154": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "McLaren_logo.svg"}}}]
                        }
                    }
                }
            }
        if "api.jolpi.ca" in url:
            return {"MRData": {"ConstructorTable": {"Constructors": [{"url": "https://en.wikipedia.org/wiki/McLaren", "name": "McLaren"}]}}}
        if "en.wikipedia.org" in url:
            return {"query": {"pages": {"1": {"pageid": 1, "pageprops": {"wikibase_item": "Q172030"}}}}}
        return None

    with patch("backend.logos._http_get_json", side_effect=mock_http), \
         patch("backend.logos._check_local_override", return_value=None), \
         patch("backend.cache.get_json", return_value=None):
        res = logos.resolve_team_logo("mclaren_test_svg", year=2024)
        assert res["logoUrl"] == "/api/logos/mclaren_test_svg.png?year=2024"
        assert res["rawThumbnailUrl"] == "https://upload.wikimedia.org/thumb/logo.svg/400px-logo.svg.png"

        # Check Commons URL has iiurlwidth=400
        commons_call = next(u for u in captured_urls if "commons.wikimedia.org" in u)
        assert "iiurlwidth=400" in commons_call


def test_failed_result_never_cached_long():
    """Verify failures or missing logos use short TTL (60s) rather than long season TTL."""
    with patch("backend.logos._check_local_override", return_value=None), \
         patch("backend.logos._http_get_json", return_value=None), \
         patch("backend.cache.set_json") as mock_cache_set:
        logos.resolve_team_logo("nonexistent_team_xyz", year=2024)
        assert mock_cache_set.called
        # Check ttl passed
        _, ttl = mock_cache_set.call_args[0][1], mock_cache_set.call_args[0][2]
        assert ttl <= 60, f"Failure was cached with TTL {ttl}s (expected <= 60s)"


def test_user_agent_present_on_download():
    """Verify descriptive User-Agent is sent on image binary download."""
    captured_req = []

    def mock_urlopen(req, *args, **kwargs):
        captured_req.append(req)
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"image-binary-data"
        return mock_resp

    with patch("backend.logos.resolve_team_logo", return_value={"rawThumbnailUrl": "https://upload.wikimedia.org/test.png"}), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen):
        logos.get_logo_image_bytes("test_team_ua", year=2024)
        assert len(captured_req) > 0
        req = captured_req[0]
        assert "User-agent" in req.headers or "User-Agent" in req.headers
        ua = req.headers.get("User-agent") or req.headers.get("User-Agent")
        assert "AI-Pitboss-F1-Telemetry" in ua
