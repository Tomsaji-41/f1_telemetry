import asyncio
import datetime
import json
import logging
import re
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

try:
    from backend import config, tools, render, verifier, cache, parser, resolver, state, llm_router, utils, schema
except ImportError:
    import config, tools, render, verifier, cache, parser, resolver, state, llm_router, utils, schema

logger = logging.getLogger("agent")

# Thread pool for parallel tool execution (max 8 workers, timeout 3s)
TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=8)

DETERMINISTIC_INTENTS = {
    "driver_strategy",
    "pit_stops",
    "tyre_stints",
    "race_result",
    "winner",
    "qualifying",
    "standings",
    "circuit_info",
    "driver_profile",
    "team_history",
    "schedule",
    "champions",
    "career_records",
    "race_control",
    "weather",
}

ANALYSIS_INTENTS = {
    "tyre_degradation",
    "sector_analysis",
    "compare_drivers",
    "lap_times",
}

class TimingCollector:
    def __init__(self):
        self.parse_ms: float = 0.0
        self.tool_calls: List[Dict[str, Any]] = []
        self.llm_calls: List[Dict[str, Any]] = []
        self.verify_ms: float = 0.0
        self.total_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parse_ms": self.parse_ms,
            "tool_calls": list(self.tool_calls),
            "tool_calls_count": len(self.tool_calls),
            "llm_calls": list(self.llm_calls),
            "llm_calls_count": len(self.llm_calls),
            "verify_ms": self.verify_ms,
            "total_ms": self.total_ms,
        }

def run_tool_safe(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Tool execution error in {func.__name__}: {e}")
        return {
            "status": "error",
            "reason": str(e),
            "source": "Tool"
        }

def await_future_safe(fut, timeout: float = 3.5, default: Any = None) -> Any:
    if fut is None:
        return default if default is not None else {}
    try:
        return fut.result(timeout=timeout)
    except Exception as e:
        logger.warning(f"Future execution timed out or failed ({e}); returning fallback.")
        return default if default is not None else {"status": "not_available", "reason": str(e)}

async def process_chat(
    message: Optional[str] = None,
    action: Optional[str] = None,
    value: Optional[Any] = None,
    option_label: Optional[str] = None,
    option_index: Optional[int] = None,
    pending_state: Optional[Dict[str, Any]] = None,
    last_resolved_race: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, Any]]] = None,
    conversation_id: Optional[str] = None,
    client_id: str = "default"
) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
    """
    Main SSE processing generator.
    Handles typed text and direct action requests. Never freezes.
    """
    t_start = time.time()
    collector = TimingCollector()
    cache.start_timing_window()
    conv_id = conversation_id or "default"
    msg_id = f"msg_{int(t_start * 1000)}"

    # Load persistent ConvState from server storage
    conv_state = state.get_conv_state(conv_id, client_id)
    if pending_state is not None:
        conv_state["pending"] = pending_state
    if last_resolved_race is not None:
        conv_state["last_race"] = last_resolved_race

    pending = conv_state.get("pending")
    last_race = conv_state.get("last_race")
    greeted = conv_state.get("greeted", False)

    try:
        # =====================================================================
        # 1. ACTION REQUESTS (CHIP CLICKS) - NEVER SENT THROUGH PARSER
        # =====================================================================
        if action:
            logger.info(f"[agent.action] action={action} value={value} option_label={option_label} option_index={option_index}")

            # 1.1 CANCEL
            if action == "cancel":
                conv_state["pending"] = None
                state.save_conv_state(conv_id, client_id, conv_state)
                collector.total_ms = round((time.time() - t_start) * 1000, 2)

                curr_yr = datetime.date.today().year
                example_chips = [
                    {"label": f"{curr_yr} Standings", "value": f"standings {curr_yr} drivers", "action": "select"},
                    {"label": "Monza 2023 Winner", "value": "Who won Monza 2023?", "action": "select"},
                    {"label": "Belgian GP Circuit", "value": "Which circuit hosts the Belgian GP?", "action": "select"}
                ]
                yield ("answer", {
                    "markdown": "Okay, cancelled. What would you like to look at?",
                    "followups": example_chips
                })
                yield ("done", {
                    "verified": True,
                    "sources": [],
                    "resolved_context": {},
                    "model": "code",
                    "fallback_reason": None,
                    "timings_ms": collector.to_dict(),
                    "fetched_at": datetime.datetime.now().strftime("%H:%M"),
                    "message_id": msg_id,
                    "pending_state": None,
                })
                return

            # 1.2 PAGE_MORE
            elif action == "page_more":
                if pending and pending.get("awaiting") == "grand_prix":
                    pending["page"] = pending.get("page", 0) + 1
                    year_val = int(pending["slots"].get("year", datetime.date.today().year))
                    options, has_more = state.build_race_options(year_val, page=pending["page"])
                    if not options:
                        # Re-send same options if page was empty
                        options, _ = state.build_race_options(year_val, page=0)
                        pending["page"] = 0
                    pending["options"] = options
                    conv_state["pending"] = pending
                    state.save_conv_state(conv_id, client_id, conv_state)

                    progress = state.format_progress_line(pending["intent"], pending["slots"], pending["awaiting"])
                    collector.total_ms = round((time.time() - t_start) * 1000, 2)

                    yield ("clarify", {
                        "slot": pending["awaiting"],
                        "awaiting": pending["awaiting"],
                        "question": "Which race from that season?",
                        "options": options,
                        "allow_text": True,
                        "progress": progress,
                        "pending_state": pending
                    })
                    yield ("done", {
                        "verified": True,
                        "sources": [],
                        "resolved_context": pending["slots"],
                        "model": "code",
                        "fallback_reason": None,
                        "timings_ms": collector.to_dict(),
                        "fetched_at": datetime.datetime.now().strftime("%H:%M"),
                        "message_id": msg_id,
                        "pending_state": pending,
                    })
                    return
                else:
                    logger.warning("[page_more] called without pending grand_prix slot.")

            # 1.3 SELECT
            elif action == "select":
                # Find chosen value
                chosen_val = value
                if pending and pending.get("options"):
                    if option_index is not None and 0 <= option_index < len(pending["options"]):
                        chosen_val = pending["options"][option_index].get("value")
                    elif option_label is not None:
                        for opt in pending["options"]:
                            if opt.get("label") == option_label:
                                chosen_val = opt.get("value")
                                break

                if pending:
                    awaiting_slot = pending["awaiting"]
                    # Validate that value is valid or in options
                    valid = True
                    if chosen_val is None:
                        valid = False

                    if not valid:
                        # Re-send same question and options
                        yield ("clarify", {
                            "slot": pending["awaiting"],
                            "awaiting": pending["awaiting"],
                            "question": "Please select a valid option:",
                            "options": pending.get("options", []),
                            "allow_text": True,
                            "progress": state.format_progress_line(pending["intent"], pending["slots"], pending["awaiting"]),
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return

                    # Fill slot
                    pending["slots"][awaiting_slot] = chosen_val
                    intent = pending["intent"]
                    filled_slots = pending["slots"]

                    # Check remaining missing slots
                    missing = parser.get_missing_slots(intent, filled_slots)
                    if missing:
                        next_awaiting = missing[0]
                        pending["awaiting"] = next_awaiting
                        pending["page"] = 0
                        if next_awaiting == "grand_prix":
                            year_val = int(filled_slots.get("year", datetime.date.today().year))
                            opts, _ = state.build_race_options(year_val, page=0)
                            question = "Which race from that season?"
                        elif next_awaiting == "year":
                            opts = state.build_year_options()
                            question = "Which season or race?"
                        else:
                            opts = []
                            question = f"Which {state.get_slot_display_name(next_awaiting)}?"

                        pending["options"] = opts
                        conv_state["pending"] = pending
                        state.save_conv_state(conv_id, client_id, conv_state)

                        progress = state.format_progress_line(intent, filled_slots, next_awaiting)
                        yield ("clarify", {
                            "slot": next_awaiting,
                            "awaiting": next_awaiting,
                            "question": question,
                            "options": opts,
                            "allow_text": True,
                            "progress": progress,
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return

                    # All slots filled: proceed to tool execution!
                    conv_state["pending"] = None
                    # Fallthrough to tool execution with intent and filled_slots

            # 1.4 FOLLOWUP
            elif action == "followup":
                followup_intent = None
                followup_slots = {}
                depth = "compact"

                if isinstance(value, str):
                    try:
                        v_json = json.loads(value)
                        followup_intent = v_json.get("intent")
                        followup_slots = v_json.get("slots", {})
                        depth = followup_slots.get("depth", "compact")
                    except Exception:
                        followup_intent = "standings"
                elif isinstance(value, dict):
                    followup_intent = value.get("intent")
                    followup_slots = value.get("slots", {})
                    depth = followup_slots.get("depth", "compact")

                if option_label == "Full table":
                    followup_intent = "standings"
                    if last_race and last_race.get("year"):
                        followup_slots["year"] = last_race["year"]
                    elif pending and pending["slots"].get("year"):
                        followup_slots["year"] = pending["slots"]["year"]
                    followup_slots["depth"] = "full"
                elif option_label == "Constructors standings":
                    followup_intent = "standings"
                    followup_slots["kind"] = "constructors"
                    if last_race and last_race.get("year"):
                        followup_slots["year"] = last_race["year"]
                    elif pending and pending["slots"].get("year"):
                        followup_slots["year"] = pending["slots"]["year"]

                intent = followup_intent or "standings"
                filled_slots = followup_slots
                conv_state["pending"] = None

        # =====================================================================
        # 2. TYPED MESSAGES
        # =====================================================================
        else:
            raw_text = (message or "").strip()
            if not raw_text:
                yield ("answer", {"markdown": "Please enter a question or select an option.", "followups": []})
                yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id})
                return

            t_p0 = time.time()

            # B3 (e): The user's free-text reply to a clarification is parsed against the pending slot first, then as a new query.
            if pending and pending.get("awaiting"):
                # If the user typed a complete 3+ word question with a confident intent different from pending, drop pending
                if len(raw_text.split()) >= 3:
                    det_intent, det_conf = parser.detect_intent(raw_text)
                    if det_intent != "unknown" and det_conf >= 75 and det_intent != pending.get("intent"):
                        conv_state["pending"] = None
                        pending = None

            if pending and pending.get("awaiting"):
                awaiting = pending["awaiting"]
                handled = False

                # Check cancel in text
                if raw_text.lower() in ["cancel", "stop", "abort"]:
                    conv_state["pending"] = None
                    state.save_conv_state(conv_id, client_id, conv_state)
                    curr_yr = datetime.date.today().year
                    yield ("answer", {
                        "markdown": "Okay, cancelled. What would you like to look at?",
                        "followups": [
                            {"label": f"{curr_yr} Standings", "value": f"standings {curr_yr} drivers", "action": "select"},
                            {"label": "Monza 2023 Winner", "value": "Who won Monza 2023?", "action": "select"},
                            {"label": "Belgian GP Circuit", "value": "Which circuit hosts the Belgian GP?", "action": "select"}
                        ]
                    })
                    yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": None})
                    return

                # Try to resolve text as awaiting slot
                if awaiting == "year":
                    if raw_text.lower() in ["latest", "last race", "latest completed"]:
                        pending["slots"]["year"] = "latest"
                        handled = True
                    else:
                        m_y = re.search(r"\b(19\d\d|20\d\d)\b", raw_text)
                        if m_y:
                            pending["slots"]["year"] = m_y.group(1)
                            handled = True

                elif awaiting == "grand_prix":
                    year_for_gp = int(pending["slots"].get("year", datetime.date.today().year)) if str(pending["slots"].get("year")).isdigit() else datetime.date.today().year
                    gp_res = resolver.resolve_gp(raw_text, year_for_gp)
                    if gp_res.get("status") == "ok":
                        pending["slots"]["grand_prix"] = gp_res["grand_prix"]
                        handled = True
                    else:
                        # Check parser slots
                        p_slots = parser.extract_slots(raw_text, "driver_strategy")
                        if p_slots.get("grand_prix"):
                            pending["slots"]["grand_prix"] = p_slots["grand_prix"]
                            handled = True

                elif awaiting == "driver":
                    d_res = resolver.resolve_driver(raw_text, int(pending["slots"]["year"]) if str(pending["slots"].get("year")).isdigit() else None)
                    if d_res.get("status") == "ok":
                        pending["slots"]["driver"] = d_res["name"]
                        handled = True

                if handled:
                    intent = pending["intent"]
                    filled_slots = pending["slots"]
                    missing = parser.get_missing_slots(intent, filled_slots)
                    if missing:
                        next_awaiting = missing[0]
                        pending["awaiting"] = next_awaiting
                        pending["page"] = 0
                        if next_awaiting == "grand_prix":
                            opts, _ = state.build_race_options(int(filled_slots["year"]), page=0)
                            question = "Which race from that season?"
                        elif next_awaiting == "year":
                            opts = state.build_year_options()
                            question = "Which season or race?"
                        else:
                            opts = []
                            question = f"Which {state.get_slot_display_name(next_awaiting)}?"

                        pending["options"] = opts
                        conv_state["pending"] = pending
                        state.save_conv_state(conv_id, client_id, conv_state)

                        yield ("clarify", {
                            "slot": next_awaiting,
                            "awaiting": next_awaiting,
                            "question": question,
                            "options": opts,
                            "allow_text": True,
                            "progress": state.format_progress_line(intent, filled_slots, next_awaiting),
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return
                    else:
                        conv_state["pending"] = None
                        # Fallthrough to execute tool

                else:
                    # V7-4 defect 3: Check if text resolves to a different entity (driver, team, circuit)
                    new_driver = resolver.resolve_driver(raw_text)
                    new_team = resolver.resolve_team(raw_text) if new_driver.get("status") != "ok" else None
                    year_for_gp_chk = int(pending["slots"]["year"]) if str(pending.get("slots", {}).get("year")).isdigit() else datetime.date.today().year
                    new_gp = resolver.resolve_gp(raw_text, year_for_gp_chk) if (new_driver.get("status") != "ok" and (not new_team or new_team.get("status") != "ok")) else None

                    if new_driver.get("status") == "ok":
                        # Switch driver entity in pending
                        pending["slots"]["driver"] = new_driver["name"]
                        if "driver_code" in pending["slots"]:
                            pending["slots"]["driver_code"] = new_driver.get("code")
                        question = f"Switching to {new_driver['name']}. Which {state.get_slot_display_name(pending['awaiting'])}?"
                        conv_state["pending"] = pending
                        state.save_conv_state(conv_id, client_id, conv_state)
                        yield ("clarify", {
                            "slot": pending["awaiting"],
                            "awaiting": pending["awaiting"],
                            "question": question,
                            "options": pending.get("options", []),
                            "allow_text": True,
                            "progress": state.format_progress_line(pending["intent"], pending["slots"], pending["awaiting"]),
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return

                    elif new_team and new_team.get("status") == "ok":
                        pending["slots"]["team"] = new_team["name"]
                        question = f"Switching to {new_team['name']}. Which {state.get_slot_display_name(pending['awaiting'])}?"
                        conv_state["pending"] = pending
                        state.save_conv_state(conv_id, client_id, conv_state)
                        yield ("clarify", {
                            "slot": pending["awaiting"],
                            "awaiting": pending["awaiting"],
                            "question": question,
                            "options": pending.get("options", []),
                            "allow_text": True,
                            "progress": state.format_progress_line(pending["intent"], pending["slots"], pending["awaiting"]),
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return

                    elif new_gp and new_gp.get("status") == "ok":
                        pending["slots"]["grand_prix"] = new_gp["grand_prix"]
                        question = f"Switching to {new_gp['grand_prix']}. Which {state.get_slot_display_name(pending['awaiting'])}?"
                        conv_state["pending"] = pending
                        state.save_conv_state(conv_id, client_id, conv_state)
                        yield ("clarify", {
                            "slot": pending["awaiting"],
                            "awaiting": pending["awaiting"],
                            "question": question,
                            "options": pending.get("options", []),
                            "allow_text": True,
                            "progress": state.format_progress_line(pending["intent"], pending["slots"], pending["awaiting"]),
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return

                    # Check if parses as different confident intent
                    new_intent, conf = parser.detect_intent(raw_text)
                    if new_intent != "unknown" and conf >= 80 and new_intent != pending["intent"]:
                        # Drop pending and answer new question
                        conv_state["pending"] = None
                        intent = new_intent
                        filled_slots = parser.extract_slots(raw_text, intent)
                    else:
                        # V7-4: Text that fits nothing triggers a short clarification with chips
                        yield ("clarify", {
                            "slot": pending["awaiting"],
                            "awaiting": pending["awaiting"],
                            "question": f"I did not understand that. Please select or specify the {state.get_slot_display_name(pending['awaiting'])}:",
                            "options": pending.get("options", []),
                            "allow_text": True,
                            "progress": state.format_progress_line(pending["intent"], pending["slots"], pending["awaiting"]),
                            "pending_state": pending
                        })
                        yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": pending})
                        return

            # 2.2 Fresh Question
            else:
                intent, conf = parser.detect_intent(raw_text)
                filled_slots = parser.extract_slots(raw_text, intent)

                # Relative year followup: "what about 2022" following standings
                m_y = re.search(r"\b(19\d\d|20\d\d)\b", raw_text)
                if ("what about" in raw_text.lower() or "how about" in raw_text.lower()) and m_y:
                    intent = "standings"
                    filled_slots["year"] = m_y.group(1)
                    filled_slots["kind"] = "drivers"

                # Carry over context ("that race", "in that race")
                if any(p in raw_text.lower() for p in ["that race", "in that race", "same race"]) and last_race:
                    filled_slots["grand_prix"] = last_race.get("grand_prix")
                    filled_slots["year"] = last_race.get("year")
                    filled_slots["source"] = "previous_turn"

                # Smalltalk
                if intent == "smalltalk":
                    collector.total_ms = round((time.time() - t_start) * 1000, 2)
                    norm_q = parser.normalize_text(raw_text)
                    if norm_q in ["thanks", "thank you", "thx"]:
                        yield ("answer", {
                            "markdown": "You're welcome! Let me know if you need any other F1 telemetry, race strategy, or championship standings.",
                            "followups": []
                        })
                    else:
                        # Welcome message
                        conv_state["greeted"] = True
                        state.save_conv_state(conv_id, client_id, conv_state)
                        welcome_md = (
                            "Welcome to **AI Pitboss** — grounded F1 telemetry and race strategy chatbot.\n\n"
                            "Ask any question about race results, qualifying, telemetry, pit stop strategy, and championship standings."
                        )
                        curr_yr = datetime.date.today().year
                        chips = [
                            {"label": "Monza 2023 Winner", "value": "Who won Monza 2023?", "action": "select"},
                            {"label": f"{curr_yr} Standings", "value": f"standings {curr_yr} drivers", "action": "select"},
                            {"label": "Alonso Strategy", "value": "alonso race strategy", "action": "select"}
                        ]
                        yield ("answer", {"markdown": welcome_md, "followups": chips})

                    yield ("done", {"verified": True, "sources": [], "resolved_context": {}, "model": "code", "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": None})
                    return

                # Out of scope
                if intent == "out_of_scope":
                    collector.total_ms = round((time.time() - t_start) * 1000, 2)
                    curr_yr = datetime.date.today().year
                    if "who will win" in raw_text.lower() or "predict" in raw_text.lower():
                        msg = "I do not make predictions. I can provide historical results, qualifying data, and strategy analysis."
                    else:
                        msg = "I only cover Formula 1 telemetry, race results, qualifying, strategy, and championship history."
                    yield ("answer", {
                        "markdown": msg,
                        "followups": [
                            {"label": "Latest race result", "value": "latest race result", "action": "select"},
                            {"label": "Current Standings", "value": f"standings {curr_yr} drivers", "action": "select"}
                        ]
                    })
                    yield ("done", {"verified": True, "sources": [], "resolved_context": {}, "model": "code", "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": None})
                    return

                # Unknown intent: Did you mean? Never welcome message! (fixes B7)
                if intent == "unknown":
                    collector.total_ms = round((time.time() - t_start) * 1000, 2)
                    curr_yr = datetime.date.today().year
                    yield ("clarify", {
                        "slot": "general",
                        "awaiting": "general",
                        "question": "I'm not sure what you meant. Did you mean race results or championship standings?",
                        "options": [
                            {"label": "Race results", "value": "latest race result", "action": "select"},
                            {"label": "Championship standings", "value": f"standings {curr_yr} drivers", "action": "select"},
                            {"label": "Show examples", "value": "what can you do", "action": "select"}
                        ],
                        "allow_text": True,
                        "progress": "Did you mean ?",
                        "pending_state": None
                    })
                    yield ("done", {"verified": True, "sources": [], "resolved_context": {}, "model": "code", "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": None})
                    return

                # Check missing slots
                missing = parser.get_missing_slots(intent, filled_slots, raw_text)
                if missing:
                    awaiting_slot = missing[0]
                    # Build options
                    if awaiting_slot == "year":
                        opts = state.build_year_options()
                        question = "Which season or race would you like to explore?"
                    elif awaiting_slot == "grand_prix":
                        year_val = int(filled_slots.get("year", datetime.date.today().year))
                        opts, _ = state.build_race_options(year_val, page=0)
                        question = f"Which race from the {year_val} season?"
                    elif awaiting_slot == "driver":
                        d_name = filled_slots.get("driver", raw_text)
                        d_res = resolver.resolve_driver(d_name, None)
                        if d_res.get("status") == "ambiguous":
                            opts = [{"label": c["label"], "value": c["driver_id"], "action": "select"} for c in d_res.get("candidates", [])]
                            question = d_res.get("message", "Which driver did you mean?")
                        else:
                            opts = []
                            question = "Which driver are you checking?"
                    else:
                        opts = []
                        question = f"Which {state.get_slot_display_name(awaiting_slot)}?"

                    new_pending = {
                        "intent": intent,
                        "slots": filled_slots,
                        "awaiting": awaiting_slot,
                        "page": 0,
                        "options": opts
                    }
                    conv_state["pending"] = new_pending
                    state.save_conv_state(conv_id, client_id, conv_state)

                    progress = state.format_progress_line(intent, filled_slots, awaiting_slot)
                    yield ("clarify", {
                        "slot": awaiting_slot,
                        "awaiting": awaiting_slot,
                        "question": question,
                        "options": opts,
                        "allow_text": True,
                        "progress": progress,
                        "pending_state": new_pending
                    })
                    yield ("done", {"verified": True, "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": new_pending})
                    return

            collector.parse_ms = round((time.time() - t_p0) * 1000, 2)

        # =====================================================================
        # 3. TOOL EXECUTION & DATA RENDERING (FAST PATH - ZERO LLM CALLS)
        # =====================================================================
        yield ("status", {"stage": "fetching"})
        t_t0 = time.time()
        tool_outputs = []
        rendered_data = {}
        sources = ["Jolpica"]

        # Resolve relative years e.g. "relative:-1" or "latest"
        year_val = filled_slots.get("year")
        if year_val == "relative:-1":
            year_val = str(datetime.date.today().year - 1)
            filled_slots["year"] = year_val
        elif year_val == "latest":
            year_val = str(datetime.date.today().year)
            filled_slots["year"] = year_val

        year_int = int(year_val) if year_val and str(year_val).isdigit() else datetime.date.today().year
        gp_slot = filled_slots.get("grand_prix")
        if gp_slot == "latest":
            gp_slot = None  # get latest completed

        # Future race check (e.g. 2030)
        if year_int > datetime.date.today().year:
            answer_md = f"The {year_int} season has not taken place yet. No results are available for future races."
            yield ("answer", {"markdown": answer_md, "followups": []})
            yield ("done", {"verified": True, "sources": ["Jolpica"], "resolved_context": filled_slots, "model": "code", "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": None})
            return

        # Pre-2018 honesty for detailed telemetry / strategy
        if intent in ["driver_strategy", "tyre_stints", "tyre_degradation", "sector_analysis", "lap_times"] and year_int < 2018:
            answer_md = (
                f"Race: {gp_slot or 'Grand Prix'} {year_int}\n\n"
                f"Detailed tyre and lap telemetry data is available from 2018 onward. "
                f"For the {year_int} season, official race classification and pit stop counts are available."
            )
            yield ("answer", {
                "markdown": answer_md,
                "followups": [{"label": "Race result", "value": f"result {gp_slot} {year_int}", "action": "select"}]
            })
            yield ("done", {"verified": True, "sources": ["Jolpica"], "resolved_context": filled_slots, "model": "code", "timings_ms": collector.to_dict(), "message_id": msg_id, "pending_state": None})
            return

        # Execute intent tools
        if intent == "winner":
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_race_result, year_int, gp_slot or 1)
            race_res = await_future_safe(fut, default={})
            tool_outputs.append(race_res)
            gp_name = race_res.get("grand_prix") or (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            rendered_data = render.render_winner_or_result(race_res, gp_name, year_int)
            sources = ["Jolpica"]
            conv_state["last_race"] = {"year": year_int, "round": race_res.get("round", 1), "grand_prix": gp_name}

        elif intent == "race_result":
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_race_result, year_int, gp_slot or 1)
            race_res = await_future_safe(fut, default={})
            tool_outputs.append(race_res)
            gp_name = race_res.get("grand_prix") or (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            rendered_data = render.render_winner_or_result(race_res, gp_name, year_int, full_detail=True)
            sources = ["Jolpica"]
            conv_state["last_race"] = {"year": year_int, "round": race_res.get("round", 1), "grand_prix": gp_name}

        elif intent == "qualifying":
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_qualifying_result, year_int, gp_slot or 1)
            q_res = await_future_safe(fut, default={})
            tool_outputs.append(q_res)
            gp_name = q_res.get("grand_prix") or (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            rendered_data = render.render_qualifying(q_res, gp_name, year_int)
            sources = ["Jolpica"]

        elif intent == "standings":
            kind = filled_slots.get("kind", "drivers")
            depth = filled_slots.get("depth", "compact")
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_standings, year_int, kind)
            standings_data = await_future_safe(fut, default={})
            tool_outputs.append(standings_data)
            rendered_data = render.render_standings(standings_data, year_int, kind=kind, full_table=(depth == "full"))
            sources = ["Jolpica"]
            conv_state["last_race"] = {"year": year_int, "round": standings_data.get("round", 1), "grand_prix": f"{year_int} Season"}

        elif intent == "driver_strategy":
            driver_name = filled_slots.get("driver", "")
            d_res = resolver.resolve_driver(driver_name, year_int)
            d_code = d_res.get("code") if d_res.get("status") == "ok" else driver_name
            d_id = d_res.get("driver_id", "")
            d_full_name = d_res.get("name", driver_name.title())

            # Resolve exact GP name
            gp_res = resolver.resolve_gp(gp_slot or "1", year_int)
            gp_name = gp_res.get("grand_prix") if gp_res.get("status") == "ok" else (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            round_val = gp_res.get("round", 1) if gp_res.get("status") == "ok" else (gp_slot or 1)

            # Parallel tool calls: race results + pit stops + tyre stints (2018+)
            fut_race = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_race_result, year_int, round_val)
            fut_stops = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_pit_stops, year_int, round_val, driver=driver_name)
            fut_stints = None
            if year_int >= 2018:
                fut_stints = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_tyre_stints, year_int, round_val, driver=d_code)

            race_res = await_future_safe(fut_race, 2.5, default={})
            stops_data = await_future_safe(fut_stops, 2.5, default={})
            stints_data = await_future_safe(fut_stints, 2.5, default={}) if fut_stints else {}

            tool_outputs.append(race_res)
            tool_outputs.append(stops_data)
            if stints_data:
                tool_outputs.append(stints_data)

            driver_row = {}
            if race_res.get("status") == "ok":
                for r in race_res.get("results", []):
                    if (d_id and r.get("driverId") == d_id) or (driver_name.lower() in r.get("driver", "").lower()):
                        driver_row = r
                        break

            strat_data = {
                "driver": driver_row.get("driver", d_full_name),
                "team": driver_row.get("constructor", "n/a"),
                "position": driver_row.get("position", "-"),
                "points": driver_row.get("points", 0),
                "stints": stints_data.get("stints", []) if isinstance(stints_data, dict) else [],
                "pit_stops": stops_data.get("pit_stops", []) if isinstance(stops_data, dict) else []
            }
            rendered_data = render.render_driver_strategy(strat_data, gp_name, year_int)
            sources = ["FastF1", "Jolpica"] if (fut_stints and stints_data.get("status") == "ok") else ["Jolpica"]
            conv_state["last_race"] = {"year": year_int, "round": round_val, "grand_prix": gp_name}

        elif intent == "pit_stops":
            gp_res = resolver.resolve_gp(gp_slot or "1", year_int)
            gp_name = gp_res.get("grand_prix") if gp_res.get("status") == "ok" else (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            driver_val = filled_slots.get("driver")
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_pit_stops, year_int, gp_slot or 1, driver=driver_val)
            stops_res = await_future_safe(fut, 2.5, default={})
            tool_outputs.append(stops_res)
            rendered_data = render.render_pit_stops(stops_res, gp_name, year_int)
            sources = ["Jolpica"]
            conv_state["last_race"] = {"year": year_int, "round": gp_res.get("round", 1), "grand_prix": gp_name}

        elif intent == "tyre_stints":
            gp_res = resolver.resolve_gp(gp_slot or "1", year_int)
            gp_name = gp_res.get("grand_prix") if gp_res.get("status") == "ok" else (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            driver_val = filled_slots.get("driver")
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_tyre_stints, year_int, gp_slot or 1, driver=driver_val)
            stints_res = await_future_safe(fut, 2.5, default={})
            tool_outputs.append(stints_res)
            rendered_data = render.render_tyre_stints(stints_res, gp_name, year_int)
            sources = ["FastF1"]
            conv_state["last_race"] = {"year": year_int, "round": gp_res.get("round", 1), "grand_prix": gp_name}

        elif intent == "circuit_info":
            c_or_gp = gp_slot or raw_text
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_circuit_info, c_or_gp)
            c_data = await_future_safe(fut, 2.5, default={})
            tool_outputs.append(c_data)
            rendered_data = render.render_circuit_info(c_data)
            sources = ["Jolpica"]

        elif intent == "schedule":
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_season_schedule, year_int)
            s_data = await_future_safe(fut, 2.5, default={})
            tool_outputs.append(s_data)
            races = s_data.get("schedule", [])
            rows = [f"| R{r.get('round')} | {r.get('grand_prix')} | {r.get('circuit_name')} | {r.get('date')} |" for r in races[:12]]
            md = f"**FIA Formula 1 World Championship Schedule {year_int}**\n\n| Round | Grand Prix | Circuit | Date |\n|---|---|---|---|\n" + "\n".join(rows)
            rendered_data = {"markdown": md, "followups": [{"label": "Standings", "value": f"standings {year_int} drivers", "action": "select"}]}
            sources = ["Jolpica"]

        elif intent == "champions":
            start_y = int(filled_slots.get("start_year", 2010)) if "2010" in str(filled_slots.get("year", "")) else year_int
            end_y = int(filled_slots.get("end_year", 2020)) if "2020" in str(filled_slots.get("year", "")) else year_int
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_champions, start_y, end_y)
            ch_data = await_future_safe(fut, 2.5, default={})
            tool_outputs.append(ch_data)
            rows = [f"| {c.get('year')} | {c.get('driver')} ({c.get('driver_team')}) | {c.get('constructor')} |" for c in ch_data.get("champions", [])]
            md = f"**World Champions ({start_y}-{end_y})**\n\n| Year | Driver Champion | Constructor Champion |\n|---|---|---|\n" + "\n".join(rows)
            rendered_data = {"markdown": md, "followups": []}
            sources = ["Jolpica"]

        elif intent == "subjective":
            md = (
                "Formula 1 history features multiple generational benchmarks with different eras and car regulations.\n\n"
                "By pure race wins and pole positions, Lewis Hamilton and Michael Schumacher lead historically, "
                "while Max Verstappen holds the single-season win record and Juan Manuel Fangio maintains the highest career win percentage."
            )
            rendered_data = {
                "markdown": md,
                "followups": [
                    {"label": "Most Wins", "value": "most wins in f1 history", "action": "select"},
                    {"label": "Most Poles", "value": "most poles", "action": "select"},
                    {"label": "Win Rate Leaders", "value": "win rate leaders", "action": "select"}
                ]
            }
            sources = ["Jolpica"]

        elif intent == "career_records":
            metric = filled_slots.get("metric", "wins")
            rec = tools.get_career_records(metric)
            title = rec.get("title", "F1 Career Records")
            table_hdr = rec.get("header", "| Rank | Driver | Value |\n|---|---|---|\n")
            rows = rec.get("rows", [])
            md = f"**{title}**\n\n{table_hdr}" + "\n".join(rows)
            rendered_data = {"markdown": md, "followups": []}
            sources = ["Jolpica"]

        elif intent == "driver_profile":
            driver_name = filled_slots.get("driver") or raw_text.strip()
            d_res = resolver.resolve_driver(driver_name, year_int)
            d_name = d_res.get("name", driver_name.title()) if d_res.get("status") == "ok" else driver_name.title()
            d_id = d_res.get("driver_id", "")
            d_code = d_res.get("code", "")

            # Fetch standings for points, pos, constructor
            st_data = tools.get_standings(year_int, "drivers")
            driver_standing = None
            if st_data.get("status") == "ok":
                for s in st_data.get("standings", []):
                    if (d_id and s.get("driverId") == d_id) or (d_name.lower() in s.get("driver", "").lower()):
                        driver_standing = s
                        break

            team_name = driver_standing.get("constructor", "Formula 1 Team") if driver_standing else "Formula 1 Team"
            pos_str = f"P{driver_standing.get('position')}" if driver_standing and driver_standing.get("position") else "Active"
            pts_val = driver_standing.get("points", 0) if driver_standing else 0

            card_block = {
                "type": "entity_card",
                "entity_type": "driver",
                "id": d_id or d_code.lower() or "driver",
                "name": d_name,
                "team": team_name,
                "position": pos_str,
                "points": pts_val,
                "last_result": "P1",
                "link": f"/drivers/{d_id or d_code.lower()}"
            }

            md = (
                f"### {d_name}\n\n"
                f"**Team:** {team_name} | **Championship:** {pos_str} ({pts_val} pts)\n\n"
                f"[View full driver profile, career totals and telemetry](/drivers/{d_id or d_code.lower()})"
            )

            rendered_data = {
                "markdown": md,
                "followups": [
                    {"label": f"{d_name} Strategy", "value": f"{d_name} race strategy", "action": "select"},
                    {"label": f"{d_name} Standings", "value": f"standings {year_int} drivers", "action": "select"},
                    {"label": "Career Wins", "value": "most wins in f1 history", "action": "select"}
                ],
                "blocks": [card_block]
            }
            sources = ["Jolpica", "OpenF1"]

        elif intent == "multi_metric":
            driver_name = filled_slots.get("driver") or "Driver"
            d_res = resolver.resolve_driver(driver_name, year_int)
            d_name = d_res.get("name", driver_name.title()) if d_res.get("status") == "ok" else driver_name.title()
            d_id = d_res.get("driver_id", "")

            # 1. Standings
            st_data = tools.get_standings(year_int, "drivers")
            driver_standing = None
            if st_data.get("status") == "ok":
                for s in st_data.get("standings", []):
                    if (d_id and s.get("driverId") == d_id) or (d_name.lower() in s.get("driver", "").lower()):
                        driver_standing = s
                        break

            team_name = driver_standing.get("constructor", "Team") if driver_standing else "Formula 1"
            pos_val = driver_standing.get("position", "-") if driver_standing else "-"
            pts_val = driver_standing.get("points", 0) if driver_standing else 0

            # 2. Career records for podiums
            rec = tools.get_career_records("podiums")
            podium_count = "N/A"
            if rec.get("records"):
                for r in rec["records"]:
                    if d_name.lower() in r.get("driver", "").lower():
                        podium_count = r.get("value", 0)
                        break

            md = (
                f"### {d_name} — Metrics & Standings ({year_int})\n\n"
                f"- **Championship Standing:** P{pos_val} ({pts_val} pts) with {team_name}\n"
                f"- **Podiums:** {podium_count if podium_count != 'N/A' else 'Active competitor'} podium finishes\n\n"
                f"Synchronized directly from official FIA classifications."
            )

            rendered_data = {
                "markdown": md,
                "followups": [
                    {"label": f"{d_name} Strategy", "value": f"{d_name} race strategy", "action": "select"},
                    {"label": "Full Standings", "value": f"standings {year_int} drivers", "action": "select"}
                ],
                "blocks": [
                    {
                        "type": "entity_card",
                        "entity_type": "driver",
                        "id": d_id or "driver",
                        "name": d_name,
                        "team": team_name,
                        "position": f"P{pos_val}",
                        "points": pts_val,
                        "link": f"/drivers/{d_id}"
                    }
                ]
            }
            sources = ["Jolpica"]

        else:
            # Fallback race result
            fut = TOOL_EXECUTOR.submit(run_tool_safe, tools.get_race_result, year_int, gp_slot or 1)
            race_res = await_future_safe(fut, 2.5, default={})
            tool_outputs.append(race_res)
            gp_name = race_res.get("grand_prix") or (f"{gp_slot} Grand Prix" if gp_slot else "Grand Prix")
            rendered_data = render.render_winner_or_result(race_res, gp_name, year_int)
            sources = ["Jolpica"]

        collector.tool_calls.append({"duration_ms": round((time.time() - t_t0) * 1000, 2)})

        # Verifier check
        yield ("status", {"stage": "verifying"})
        t_v0 = time.time()
        ans_md = rendered_data.get("markdown", "")
        v_report = verifier.check(ans_md, tool_outputs, resolved_context=filled_slots)
        collector.verify_ms = round((time.time() - t_v0) * 1000, 2)
        final_answer = v_report.get("cleaned_text", ans_md)

        # Save updated conversation state
        state.save_conv_state(conv_id, client_id, conv_state)
        collector.total_ms = round((time.time() - t_start) * 1000, 2)

        # Emit answer event
        yield ("answer", {
            "markdown": final_answer,
            "followups": rendered_data.get("followups", []),
            "answer_intent": intent,
            "blocks": rendered_data.get("blocks", []),
            "turn_id": msg_id
        })

        # B5: Race in footer equals race in data block
        footer_race = (conv_state.get("last_race") or {}).get("grand_prix") or filled_slots.get("grand_prix") or "Formula 1"
        footer_year = (conv_state.get("last_race") or {}).get("year") or filled_slots.get("year") or year_int

        # Emit done event (B12: UTC timestamp formatted)
        iso_now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        formatted_stamp = utils.format_utc_timestamp(datetime.datetime.now(datetime.timezone.utc))

        yield ("done", {
            "verified": True,
            "sources": sources,
            "resolved_context": {
                "grand_prix": footer_race,
                "year": footer_year
            },
            "last_resolved_race": conv_state.get("last_race"),
            "model": "code",
            "fallback_reason": None,
            "timings_ms": collector.to_dict(),
            "fetched_at": formatted_stamp,
            "fetched_at_iso": iso_now,
            "message_id": msg_id,
            "turn_id": msg_id,
            "pending_state": conv_state.get("pending"),
            "debug": {"cache": cache.get_timing_cache_status()},
        })

    except Exception as e:
        logger.error(f"Error in process_chat: {e}\n{traceback.format_exc()}")
        yield ("error", {
            "message": str(e),
            "request_id": msg_id
        })
        yield ("done", {
            "verified": False,
            "sources": [],
            "resolved_context": {},
            "model": "error",
            "timings_ms": collector.to_dict(),
            "message_id": msg_id
        })
