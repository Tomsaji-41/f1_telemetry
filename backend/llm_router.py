import asyncio
import inspect
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator

try:
    from backend import config, verifier
except ImportError:
    import config, verifier

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from groq import AsyncGroq, Groq
except ImportError:
    AsyncGroq = None
    Groq = None

logger = logging.getLogger("llm_router")

# Circuit breaker state
_fail_times: List[float] = []
_skip_until: float = 0.0

# Active clients (can be monkeypatched in tests)
gem = None
groq = None

def _get_gemini_client():
    global gem
    if gem is not None:
        return gem
    if config.GEMINI_API_KEY and genai is not None:
        try:
            gem = genai.Client(api_key=config.GEMINI_API_KEY)
            return gem
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini Client: {e}")
    return None

def _get_groq_async_client():
    global groq
    if groq is not None:
        return groq
    if config.GROQ_API_KEY and AsyncGroq is not None:
        try:
            groq = AsyncGroq(api_key=config.GROQ_API_KEY)
            return groq
        except Exception as e:
            logger.warning(f"Failed to initialize Groq Async Client: {e}")
    return None

def _gemini_blocked() -> bool:
    return time.time() < _skip_until

def _record_gemini_failure():
    global _skip_until
    now = time.time()
    _fail_times.append(now)
    _fail_times[:] = [t for t in _fail_times if now - t < 60]
    if len(_fail_times) >= 2:
        _skip_until = now + 300.0
        logger.warning(f"Circuit breaker tripped: Gemini failed {len(_fail_times)} times in 60s. Skipping Gemini for 5 minutes.")

def reset_circuit_breaker():
    """Reset circuit breaker state (useful for tests)."""
    global _skip_until, _fail_times
    _skip_until = 0.0
    _fail_times.clear()

SYSTEM_PROMPT = """You are Pitboss, an expert F1 Lead Strategy Engineer and Data Analyst.
GROUNDING DIRECTIVES:
1. Provide concise, direct pit-wall insights based strictly on the provided data.
2. Every number, position, and lap time must match the data exactly.
3. No speculation or invented causes (e.g. traffic, degradation, mechanical issues) unless explicitly stated in the data.
4. Keep plain text readable, professional, and clear."""

def sanitize_output(text: str) -> str:
    """Removes leftover markdown symbols, non-breaking hyphens, and weird spaces."""
    if not text:
        return ""
    text = re.sub(r'[*_#|`~]', '', text)
    text = re.sub(r'[\u00A0\u202F\u2000-\u200A]', ' ', text)
    text = re.sub(r'[\u2010-\u2015\u2212]', '-', text)
    text = text.replace('Δ', 'Delta ')
    return text.strip()

def render_fast_path_table(data: Any = None) -> str:
    """
    Renders code-rendered fast-path table with the busy message.
    Guarantees a non-empty fallback reply.
    """
    header = "The analysis service is busy, showing the data only.\n"
    if not data:
        return header + "\n| Status | Note |\n| --- | --- |\n| Telemetry Service | Data temporarily displayed in fallback mode |"

    if isinstance(data, list):
        if not data:
            return header + "\n| Status | Note |\n| --- | --- |\n| Telemetry Service | Data temporarily displayed in fallback mode |"
        first = data[0]
        if isinstance(first, dict):
            keys = [k for k in first.keys() if not k.startswith("_")]
            cols = keys[:6] if keys else ["Item", "Value"]
            th = "| " + " | ".join(c.capitalize() for c in cols) + " |"
            sep = "| " + " | ".join("---" for _ in cols) + " |"
            rows = []
            for row in data[:15]:
                if isinstance(row, dict):
                    vals = [str(row.get(c, "-")) for c in cols]
                    rows.append("| " + " | ".join(vals) + " |")
                else:
                    rows.append(f"| {str(row)} |")
            return header + "\n" + th + "\n" + sep + "\n" + "\n".join(rows)

    if isinstance(data, dict):
        # Key-value table
        rows = [f"| {k} | {v} |" for k, v in list(data.items())[:15]]
        return header + "\n| Metric | Value |\n| --- | --- |\n" + "\n".join(rows)

    return header + f"\n| Data Summary |\n| --- |\n| {str(data)[:200]} |"

async def _gemini_stream(system: str, user: str, q: asyncio.Queue):
    client = _get_gemini_client()
    if client is None:
        await q.put(("gemini_error", RuntimeError("Gemini client not initialized")))
        return
    try:
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.1,
            max_output_tokens=600,
            thinking_config=types.ThinkingConfig(thinking_budget=0) if (types and hasattr(types, "ThinkingConfig")) else None
        )
        stream_call = client.aio.models.generate_content_stream(
            model=config.GEMINI_MODEL,
            contents=user,
            config=cfg
        )
        stream = await stream_call if inspect.isawaitable(stream_call) else stream_call
        async for chunk in stream:
            text = chunk.text if hasattr(chunk, "text") else str(chunk)
            if text:
                await q.put(("gemini", text))
        await q.put(("gemini", None))
    except Exception as e:
        await q.put(("gemini_error", e))

async def _groq_stream(system: str, user: str, q: asyncio.Queue):
    client = _get_groq_async_client()
    if client is None:
        await q.put(("groq_error", RuntimeError("Groq async client not initialized")))
        return
    try:
        stream_call = client.chat.completions.create(
            model=config.GROQ_MODEL,
            temperature=0.1,
            max_tokens=600,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
        )
        stream = await stream_call if inspect.isawaitable(stream_call) else stream_call
        async for ev in stream:
            if hasattr(ev, "choices") and ev.choices:
                delta = ev.choices[0].delta
                t = getattr(delta, "content", None) if delta else None
                if t:
                    await q.put(("groq", t))
        await q.put(("groq", None))
    except Exception as e:
        await q.put(("groq_error", e))

def _drain_queue(q: asyncio.Queue):
    """Drain all items from queue."""
    while not q.empty():
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            break

async def narrate(system: str, user: str, tool_data: Optional[Any] = None, meta: Optional[Dict[str, Any]] = None) -> AsyncGenerator[Tuple[str, str], None]:
    """
    Async generator yielding (model, text).
    Hedges Gemini with Groq per STEP 4B routing rules.
    If both fail, yields ("fast_path", fast_path_table).
    """
    q: asyncio.Queue = asyncio.Queue()
    tasks: Dict[str, asyncio.Task] = {}
    winner: Optional[str] = None
    fallback_reason: Optional[str] = None
    t0 = time.time()
    gemini_yielded_chunks = False

    def update_meta():
        if meta is not None:
            meta["fallback_reason"] = fallback_reason
            meta["model"] = winner

    # Check circuit breaker
    if _gemini_blocked() or not config.GEMINI_API_KEY:
        winner = "groq"
        fallback_reason = "circuit_breaker" if _gemini_blocked() else "no_gemini_key"
        update_meta()
        tasks["groq"] = asyncio.create_task(_groq_stream(system, user, q))
    else:
        tasks["gemini"] = asyncio.create_task(_gemini_stream(system, user, q))

    try:
        while True:
            timeout = None
            if winner is None and "gemini" in tasks and "groq" not in tasks:
                # First-token timeout
                elapsed = time.time() - t0
                timeout = max(0.01, config.GEMINI_FIRST_TOKEN_TIMEOUT_S - elapsed)
            elif winner == "gemini":
                # Total-time guard
                elapsed = time.time() - t0
                remaining = config.GEMINI_TOTAL_TIMEOUT_S - elapsed
                if remaining <= 0:
                    raise asyncio.TimeoutError("Gemini total timeout exceeded")
                timeout = max(0.01, remaining)

            try:
                src, text = await asyncio.wait_for(q.get(), timeout)
            except asyncio.TimeoutError:
                if winner is None:
                    # First token timeout -> Hedge by starting Groq
                    _record_gemini_failure()
                    fallback_reason = "timeout"
                    update_meta()
                    tasks["groq"] = asyncio.create_task(_groq_stream(system, user, q))
                    continue
                elif winner == "gemini":
                    # Mid-stream total timeout -> Fail over to Groq
                    _record_gemini_failure()
                    fallback_reason = "timeout"
                    update_meta()
                    if "gemini" in tasks:
                        tasks["gemini"].cancel()
                    _drain_queue(q)
                    if gemini_yielded_chunks:
                        yield ("reset", "")
                        gemini_yielded_chunks = False
                    winner = "groq"
                    tasks["groq"] = asyncio.create_task(_groq_stream(system, user, q))
                    continue
                else:
                    raise

            # Process queue messages
            if src == "gemini_error":
                _record_gemini_failure()
                err_str = str(text).lower()
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    fallback_reason = "rate_limit"
                else:
                    fallback_reason = "error"
                update_meta()

                if "gemini" in tasks:
                    tasks["gemini"].cancel()
                _drain_queue(q)

                if winner == "gemini" and gemini_yielded_chunks:
                    yield ("reset", "")
                    gemini_yielded_chunks = False

                if "groq" not in tasks:
                    winner = "groq"
                    tasks["groq"] = asyncio.create_task(_groq_stream(system, user, q))
                continue

            if src == "groq_error":
                if "groq" in tasks:
                    tasks["groq"].cancel()
                # If winner was groq or groq was fallback, both failed
                if winner == "groq" or "gemini" not in tasks or tasks["gemini"].done():
                    table = render_fast_path_table(tool_data)
                    update_meta()
                    yield ("fast_path", table)
                    return
                continue

            # Regular tokens
            if winner is None:
                winner = src
                if winner == "groq" and fallback_reason is None:
                    fallback_reason = "timeout"
                update_meta()
                for name, t in list(tasks.items()):
                    if name != winner:
                        t.cancel()

            if src != winner:
                continue

            if text is None:
                # End of winning stream
                update_meta()
                return

            if winner == "gemini":
                gemini_yielded_chunks = True

            yield (src, text)

    except Exception as e:
        logger.warning(f"Error in narrate loop: {e}")
        if winner == "gemini" or "gemini" in tasks:
            _record_gemini_failure()
            if fallback_reason is None:
                fallback_reason = "error"
        update_meta()
        if "groq" not in tasks:
            _drain_queue(q)
            if gemini_yielded_chunks:
                yield ("reset", "")
            winner = "groq"
            tasks["groq"] = asyncio.create_task(_groq_stream(system, user, q))
            while True:
                try:
                    src, text = await asyncio.wait_for(q.get(), timeout=config.GEMINI_TOTAL_TIMEOUT_S)
                    if src == "groq_error":
                        break
                    if src == "groq":
                        if text is None:
                            update_meta()
                            return
                        yield ("groq", text)
                except Exception:
                    break
        table = render_fast_path_table(tool_data)
        yield ("fast_path", table)

    finally:
        update_meta()
        for t in tasks.values():
            if not t.done():
                t.cancel()

async def generate_response(system: str, user: str, tool_data: Optional[Any] = None) -> Dict[str, Any]:
    """
    Executes narrate, discards partial tokens if mid-stream fallback occurs,
    applies verifier rules ('no causes unless data says so'), and returns metadata.
    """
    t0 = time.time()
    chunks: List[str] = []
    actual_model: Optional[str] = None
    meta: Dict[str, Any] = {"fallback_reason": None, "model": None}

    async for src, chunk in narrate(system, user, tool_data=tool_data, meta=meta):
        if src == "reset":
            chunks.clear()
            continue
        actual_model = src
        chunks.append(chunk)

    duration_ms = round((time.time() - t0) * 1000, 2)
    raw_text = "".join(chunks)

    fallback_reason = meta.get("fallback_reason")
    if actual_model == "gemini":
        fallback_reason = None
    elif actual_model == "fast_path":
        fallback_reason = fallback_reason or "error"

    # Verifier and "no causes unless the data says so" applies to both models identically
    cleaned_text = verifier.clean(raw_text, tool_outputs=tool_data if isinstance(tool_data, list) else ([tool_data] if tool_data else []))

    return {
        "text": cleaned_text,
        "answer": cleaned_text,
        "model": actual_model or "groq",
        "fallback_reason": fallback_reason,
        "timings_ms": duration_ms
    }


class LLMRouter:
    """LLMRouter supporting backward compatibility and Step 4B routing."""

    def __init__(self):
        self.groq_key = config.GROQ_API_KEY
        self.gemini_key = config.GEMINI_API_KEY

    def render_fast_path_table(self, data: Any = None) -> str:
        return render_fast_path_table(data)

    async def narrate(self, system: str, user: str, tool_data: Optional[Any] = None) -> AsyncGenerator[Tuple[str, str], None]:
        async for item in narrate(system, user, tool_data=tool_data):
            yield item

    async def generate_response(self, system: str, user: str, tool_data: Optional[Any] = None) -> Dict[str, Any]:
        return await generate_response(system, user, tool_data=tool_data)

    def generate_completion(self, system_prompt: str, user_prompt: str, tool_data: Optional[Any] = None) -> str:
        """Synchronous wrapper for generating completions."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(asyncio.run, generate_response(system_prompt, user_prompt, tool_data)).result()
        else:
            res = loop.run_until_complete(generate_response(system_prompt, user_prompt, tool_data))
        return res.get("text", "")

    def generate_concise_report(self, race_facts: dict) -> str:
        user_prompt = f"""
Generate a concise F1 Pit-Wall Strategy Brief strictly based on these facts:
- Event: {race_facts.get('event_name')} ({race_facts.get('year')})
- Location: {race_facts.get('location')}
- Winner: {race_facts.get('winner')}
- Total Laps: {race_facts.get('total_laps')}
- Incidents: {race_facts.get('incidents', [])}
- Top Results: {race_facts.get('results', [])[:6]}
"""
        return self.generate_completion(SYSTEM_PROMPT, user_prompt, tool_data=race_facts)

    def analyze_strategy(self, prompt: str, mode: str = "groq") -> str:
        return self.generate_completion(SYSTEM_PROMPT, prompt)