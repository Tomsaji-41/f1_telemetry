"""
backend/charts/schema.py
Shared Pydantic response contract for all /api/charts/* endpoints.
Adheres strictly to Phase 1.4:
status in {"ok", "loading", "not_available", "error"}
Never returns "ok" with an empty series.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator, ConfigDict

ChartStatus = Literal["ok", "loading", "not_available", "error"]

class ChartResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: ChartStatus
    source: str
    coverage_note: Optional[str] = None
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"))
    message: Optional[str] = None
    series: Optional[List[Any]] = None
    axes: Optional[Dict[str, Any]] = None
    job_id: Optional[str] = None
    eta_s: Optional[int] = None
    year: Optional[int] = None
    round: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def validate_contract(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        # Normalize incoming statuses
        s = values.get("status", "ok")
        if s in ("preparing", "pending", "running"):
            s = "loading"
        elif s in ("empty", "outside_coverage", "not_ingested", "not_published_yet"):
            s = "not_available"
        elif s not in ("ok", "loading", "not_available", "error"):
            s = "error" if "error" in str(s).lower() else "not_available"

        # Rule: A route must NEVER return "ok" with an empty series
        if s == "ok":
            series_val = values.get("series")
            if series_val is not None and isinstance(series_val, list) and len(series_val) == 0:
                # Check other list fields
                other_has_data = any(
                    isinstance(values.get(k), list) and len(values.get(k)) > 0
                    for k in ("rows", "stints", "stops", "points", "laps", "drivers")
                )
                if not other_has_data:
                    s = "not_available"
                    if not values.get("coverage_note"):
                        values["coverage_note"] = "No series data recorded for this session."

        values["status"] = s
        if "fetched_at" not in values or not values["fetched_at"]:
            values["fetched_at"] = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

        return values
