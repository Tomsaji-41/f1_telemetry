from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class EntityCardBlock(BaseModel):
    type: str = "entity_card"
    entity_type: str  # driver | team | circuit
    id: str
    name: str
    subtitle: Optional[str] = None
    team: Optional[str] = None
    number: Optional[str] = None
    points: Optional[Union[int, float, str]] = None
    position: Optional[Union[int, str]] = None
    last_result: Optional[str] = None
    link: Optional[str] = None
    badges: List[str] = Field(default_factory=list)

class TableBlock(BaseModel):
    type: str = "table"
    title: Optional[str] = None
    headers: List[str]
    rows: List[List[Any]]
    total_count: Optional[int] = None
    expanded: bool = False

class ChartBlock(BaseModel):
    type: str = "chart"
    chart: str  # Whitelisted chart ID
    title: str
    params: Dict[str, Any] = Field(default_factory=dict)
    series: List[Dict[str, Any]] = Field(default_factory=list)
    axes: Dict[str, Any] = Field(default_factory=dict)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)

class StatusBlock(BaseModel):
    type: str = "status_card"
    status: str  # not_ingested | not_published_yet | outside_coverage | source_error | genuinely_empty
    source: str
    reason: str
    retry_available: bool = False
    estimated_seconds: Optional[int] = None

class FollowupChip(BaseModel):
    label: str
    action: str = "select"  # select | followup | cancel | page_more
    value: Optional[Union[str, Dict[str, Any]]] = None
    intent: Optional[str] = None
    slots: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    turn_id: str
    answer_intent: str
    blocks: List[Dict[str, Any]] = Field(default_factory=list)
    markdown: str = ""
    followups: List[Dict[str, Any]] = Field(default_factory=list)
    assumption_chip: Optional[Dict[str, Any]] = None
    sources: List[str] = Field(default_factory=list)
    fetched_at: str = ""
    race_context: Optional[str] = None
    verified: bool = True
