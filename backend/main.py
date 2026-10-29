import asyncio
import datetime
import inspect
import json
import logging
import time
import traceback
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, Union
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

try:
    from backend import config, tools, agent, cache, resolver, utils
    from backend.sources import jolpica, fastf1_src, openf1_src
    from backend.charts.routes import router as charts_router
    from backend.charts import jobs as chart_jobs
    from backend.charts import loader as chart_loader
    from backend.api_data import router as data_router
except ImportError:
    import config, tools, agent, cache, resolver, utils
    from sources import jolpica, fastf1_src, openf1_src
    from charts.routes import router as charts_router
    from charts import jobs as chart_jobs
    from charts import loader as chart_loader
    from api_data import router as data_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pitboss")

config.validate()

# In-memory recent request metrics
RECENT_METRICS: List[Dict[str, Any]] = []

import os
import sys

is_testing = bool(
    os.getenv("PYTEST_CURRENT_TEST")
    or any("pytest" in arg.lower() for arg in sys.argv)
    or os.getenv("TESTING", "").lower() in ("1", "true")
)
limiter = Limiter(key_func=get_remote_address, enabled=not is_testing)

# CORS restricted to Next.js dev server per spec
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

class BoundedConversationStore:
    def __init__(self, max_clients: int = 500, ttl_seconds: int = 3600):
        self.max_clients = max_clients
        self.ttl = ttl_seconds
        self._data: OrderedDict[str, Dict[str, Any]] = OrderedDict()

    def get(self, key: str, default=None):
        if key not in self._data:
            return default
        entry = self._data[key]
        if time.time() - entry["timestamp"] > self.ttl:
            del self._data[key]
            return default
        self._data.move_to_end(key)
        return entry["conversations"]

    def __setitem__(self, key: str, convs: Any):
        if key in self._data:
            del self._data[key]
        elif len(self._data) >= self.max_clients:
            self._data.popitem(last=False)
        self._data[key] = {"timestamp": time.time(), "conversations": convs}

    def __getitem__(self, key: str):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __contains__(self, key: str):
        return self.get(key) is not None

CONVERSATIONS_STORE = BoundedConversationStore(max_clients=500, ttl_seconds=3600)

class ChatHistoryItem(BaseModel):
    role: str
    text: Optional[str] = None
    content: Optional[str] = None

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    text: Optional[str] = None
    message: Optional[str] = None
    prompt: Optional[str] = None
    action: Optional[str] = None
    chip: Optional[Dict[str, Any]] = None
    turn_id: Optional[str] = None
    value: Optional[Any] = None
    option_label: Optional[str] = None
    option_index: Optional[int] = None
    history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    pending_state: Optional[Dict[str, Any]] = None
    last_resolved_race: Optional[Dict[str, Any]] = None
    year: Optional[int] = None
    round_num: Optional[int] = None

import threading
from fastapi.responses import StreamingResponse

def _prefetch_worker():
    """Background startup prefetch (Rule S2). Must never crash startup."""
    try:
        current_year = datetime.date.today().year
        logger.info(f"[startup] Prefetching {current_year} season schedule and standings...")
        tools.get_season_schedule(current_year)
        tools.get_standings(current_year, kind="drivers")
        tools.get_standings(current_year, kind="constructors")
        logger.info("[startup] Background prefetch complete.")
    except Exception as e:
        logger.warning(f"[startup] Non-fatal background prefetch error: {e}")

def get_all_registered_routes(obj) -> List[Any]:
    res = []
    for r in getattr(obj, 'routes', []):
        if hasattr(r, 'original_router'):
            res.extend(get_all_registered_routes(r.original_router))
        elif hasattr(r, 'routes'):
            res.extend(get_all_registered_routes(r))
        elif hasattr(r, 'path'):
            res.append(r)
    return res

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager (replaces deprecated on_event)."""
    # ── Startup: Cache Hygiene (Phase 1.5) ──────────────────────────────────
    try:
        cache.purge_bad_entries()
    except Exception as e:
        logger.warning(f"[startup] Cache purge error (ignored): {e}")

    # ── Banner ──────────────────────────────────────────────────────────────
    try:
        from pathlib import Path
        banner_file = Path(__file__).resolve().parent / "banner.txt"
        if banner_file.exists():
            banner_text = banner_file.read_text(encoding="utf-8")
            print(banner_text, flush=True)
            logger.info("\n" + banner_text)
    except Exception as e:
        logger.debug(f"[startup] Banner display error (ignored): {e}")

    try:
        prefetch_thread = threading.Thread(target=_prefetch_worker, daemon=True)
        prefetch_thread.start()
    except Exception as e:
        logger.warning(f"[startup] Failed to start prefetch worker (ignored): {e}")

    try:
        chart_jobs.start_cleanup()
    except Exception as e:
        logger.warning(f"[startup] Failed to start chart job cleanup (ignored): {e}")

    # Warm FastF1 cache for latest completed race (non-blocking daemon thread)
    try:
        threading.Thread(target=chart_loader.warm_latest, daemon=True, name="fastf1-warmup").start()
    except Exception as e:
        logger.warning(f"[startup] FastF1 warm-up failed (ignored): {e}")

    try:
        all_routes = get_all_registered_routes(app)
        logger.info("=== REGISTERED BACKEND ROUTES ===")
        print(f"=== REGISTERED BACKEND ROUTES ({len(all_routes)} total) ===", flush=True)
        for route in all_routes:
            methods = getattr(route, "methods", None)
            methods_str = ",".join(sorted(methods)) if methods else "ANY"
            path = getattr(route, "path", getattr(route, "path_format", str(route)))
            print(f"Route: {methods_str:<15} {path}", flush=True)
            logger.info(f"Route: {methods_str:<15} {path}")
    except Exception as e:
        logger.warning(f"[startup] Route listing error (ignored): {e}")

    yield  # ── App runs here ─────────────────────────────────────────────────
    # (Shutdown hooks go here if needed)

# Create app AFTER lifespan is defined
app = FastAPI(title="Telemetra Engine", version="7.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(charts_router)
app.include_router(data_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Client-Id"],
    expose_headers=["*"],
)

@app.get("/")
def root():
    return {
        "service": "AI Pitboss Grounded F1 Engine",
        "version": "4.0.0",
        "status": "online",
        "endpoints": [
            "/api/chat",
            "/api/chat/stream",
            "/api/conversations",
            "/api/metrics",
            "/api/health",
            "/api/live"
        ]
    }

@app.post("/api/chat")
@limiter.limit("60/minute")
async def chat_endpoint(req: ChatRequest, request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 65536:
        raise HTTPException(status_code=413, detail="Payload too large")

    text = (req.text or "").strip()
    if not text and not req.action and not req.chip:
        raise HTTPException(status_code=422, detail="Missing required 'text' or 'action' field in chat request.")
    if text and len(text) > 1000:
        raise HTTPException(status_code=400, detail="Message exceeds maximum length of 1000 characters.")

    client_id = request.headers.get("x-client-id", "default")
    conv_id = req.conversation_id or f"conv_{client_id}"

    clarify_resp = None
    answer_resp = None
    error_resp = None

    async for ev_type, ev_data in agent.process_chat(
        message=text if not req.action and not req.chip else None,
        action=req.action,
        value=req.value,
        chip=req.chip,
        option_label=req.option_label,
        option_index=req.option_index,
        pending_state=req.pending_state,
        last_resolved_race=req.last_resolved_race,
        history=req.history,
        conversation_id=conv_id,
        client_id=client_id
    ):
        if ev_type == "clarify":
            clarify_resp = ev_data
        elif ev_type == "answer":
            answer_resp = ev_data
        elif ev_type == "error":
            error_resp = ev_data

    turn_id = getattr(req, "turn_id", None) or f"turn_{int(time.time() * 1000)}"

    if error_resp:
        return {"type": "error", "message": error_resp.get("message"), "turn_id": turn_id}
    if clarify_resp:
        return {
            "type": "clarify",
            "turn_id": clarify_resp.get("turn_id") or clarify_resp.get("message_id") or turn_id,
            "awaiting": clarify_resp.get("awaiting", clarify_resp.get("slot")),
            "slot": clarify_resp.get("slot"),
            "question": clarify_resp.get("question"),
            "options": clarify_resp.get("options", []),
            "progress": clarify_resp.get("progress"),
            "pending_state": clarify_resp.get("pending_state")
        }
    if answer_resp:
        return {
            "type": "answer",
            "turn_id": answer_resp.get("turn_id") or answer_resp.get("message_id") or turn_id,
            "answer_intent": answer_resp.get("answer_intent"),
            "markdown": answer_resp.get("markdown"),
            "followups": answer_resp.get("followups", []),
            "blocks": answer_resp.get("blocks", [])
        }
    return {"type": "answer", "turn_id": turn_id, "markdown": "No response generated."}

@app.post("/api/chat/stream")
@limiter.limit("60/minute")
async def chat_stream_endpoint(req: ChatRequest, request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 65536:
        raise HTTPException(status_code=413, detail="Payload too large")

    client_id = request.headers.get("x-client-id", "default")
    conv_id = req.conversation_id or f"conv_{client_id}"
    text = (req.text or req.message or req.prompt or "").strip()

    if not text and not req.action and not req.chip:
        raise HTTPException(status_code=422, detail="Missing question / message / action.")
    if text and len(text) > 1000:
        raise HTTPException(status_code=400, detail="Message exceeds maximum length of 1000 characters.")

    async def event_generator():
        emitted_done = False
        queue: asyncio.Queue = asyncio.Queue()

        async def producer():
            try:
                async for ev_type, ev_data in agent.process_chat(
                    message=text if not req.action and not req.chip else None,
                    action=req.action,
                    value=req.value,
                    chip=req.chip,
                    option_label=req.option_label,
                    option_index=req.option_index,
                    pending_state=req.pending_state,
                    last_resolved_race=req.last_resolved_race,
                    history=req.history,
                    conversation_id=conv_id,
                    client_id=client_id
                ):
                    await queue.put((ev_type, ev_data))
                await queue.put(("__stream_done__", None))
            except Exception as e:
                logger.error(f"Error in stream generator: {e}\n{traceback.format_exc()}")
                await queue.put(("error", {"error": str(e), "message": str(e)}))
                await queue.put(("__stream_done__", None))

        producer_task = asyncio.create_task(producer())

        try:
            while True:
                try:
                    ev_type, ev_data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    if ev_type == "__stream_done__":
                        break
                    if ev_type == "done":
                        emitted_done = True
                    payload = json.dumps(ev_data)
                    yield f"event: {ev_type}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield f"event: heartbeat\ndata: {json.dumps({'time': time.time()})}\n\n"
        finally:
            if not producer_task.done():
                producer_task.cancel()
            if not emitted_done:
                yield f"event: done\ndata: {json.dumps({'verified': False, 'message': 'Stream ended'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/api/conversations")
def get_conversations(request: Request):
    client_id = request.headers.get("x-client-id", "default")
    return {
        "client_id": client_id,
        "conversations": CONVERSATIONS_STORE.get(client_id, [])
    }

@app.post("/api/conversations")
def save_conversation(conv: Dict[str, Any], request: Request):
    client_id = request.headers.get("x-client-id", "default")
    if client_id not in CONVERSATIONS_STORE:
        CONVERSATIONS_STORE[client_id] = []

    conv_id = conv.get("id") or f"conv_{int(time.time() * 1000)}"
    conv["id"] = conv_id
    conv["updated_at"] = datetime.datetime.now().isoformat()

    existing_idx = next((i for i, c in enumerate(CONVERSATIONS_STORE[client_id]) if c.get("id") == conv_id), None)
    if existing_idx is not None:
        CONVERSATIONS_STORE[client_id][existing_idx] = conv
    else:
        CONVERSATIONS_STORE[client_id].insert(0, conv)

    return {"status": "ok", "conversation": conv}

@app.get("/api/metrics")
def metrics_endpoint():
    intent_timings: Dict[str, List[float]] = {}
    for m in RECENT_METRICS:
        intent = m.get("intent", "other")
        t_total = m.get("timings", {}).get("total_ms", 0.0)
        intent_timings.setdefault(intent, []).append(t_total)

    stats = {}
    for intent, times in intent_timings.items():
        sorted_times = sorted(times)
        n = len(sorted_times)
        p50 = sorted_times[int(0.50 * n)] if n > 0 else 0.0
        p95 = sorted_times[min(int(0.95 * n), n - 1)] if n > 0 else 0.0
        stats[intent] = {
            "count": n,
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2)
        }

    return {
        "count": len(RECENT_METRICS),
        "by_intent": stats,
        "metrics": list(RECENT_METRICS)
    }

@app.get("/api/health")
@app.get("/health")
def health_endpoint():
    # Source reachability test
    jolpica_ok = False
    try:
        s = jolpica.fetch_schedule(datetime.date.today().year)
        jolpica_ok = s.get("status") == "ok"
    except Exception:
        pass

    return {
        "status": "healthy",
        "fetched_at": utils.format_utc_timestamp(),
        "sources": ["Jolpica", "FastF1", "OpenF1"],
        "keys": {
            "gemini_configured": bool(config.GEMINI_API_KEY),
            "groq_configured": bool(config.GROQ_API_KEY)
        },
        "models": {
            "gemini": config.GEMINI_MODEL,
            "groq": config.GROQ_MODEL
        },
        "cache": cache.get_cache_stats(),
        "source_reachability": {
            "jolpica": "reachable" if jolpica_ok else "unreachable",
            "fastf1": "available" if fastf1_src.fastf1 else "unavailable",
            "openf1": "reachable"
        }
    }

@app.get("/api/live")
def live_endpoint():
    """Live session feed from OpenF1."""
    return openf1_src.fetch_live_session()

@app.get("/api/driver-image/{driver}")
def driver_image_endpoint(driver: str, year: Optional[int] = None):
    return openf1_src.fetch_driver_image(driver, year=year)

@app.get("/api/tool/{name}")
def run_tool_debug(name: str, request: Request):
    """Debug only: execute tool directly by name."""
    tool_map = {f.__name__: f for f in tools.TOOL_REGISTRY}
    fn = tool_map.get(name)
    if not fn:
        raise HTTPException(status_code=404, detail=f"Tool '{name}' not found. Available: {list(tool_map.keys())}")

    raw_params = dict(request.query_params)
    sig = inspect.signature(fn)
    cast_params = {}
    for param_name, param in sig.parameters.items():
        if param_name in raw_params:
            val = raw_params[param_name]
            if param.annotation == int:
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif param.annotation == float:
                try:
                    val = float(val)
                except ValueError:
                    pass
            cast_params[param_name] = val

    try:
        result = fn(**cast_params)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Backward compatibility endpoints for existing frontend tabs
@app.get("/api/v1/facts/{year}/{round_num}")
@app.get("/api/v1/race/{year}/{round_num}")
def get_race_facts_compat(year: int, round_num: int):
    return tools.get_race_result(year, round_num)

@app.get("/api/v1/telemetry/{year}/{round_num}/{driver1}/{driver2}")
def get_telemetry_compat(year: int, round_num: int, driver1: str, driver2: str):
    return tools.compare_drivers(year, round_num, driver1, driver2)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=config.BACKEND_HOST, port=config.BACKEND_PORT, reload=True)
