import time
import json
import requests

API_URL = "http://127.0.0.1:8000"

def send_chat(msg, client_id="test-client", pending_state=None, action=None, value=None):
    headers = {
        "Content-Type": "application/json",
        "X-Client-Id": client_id,
        "X-Request-Id": f"req-{int(time.time()*1000)}"
    }
    payload = {"message": msg}
    if pending_state is not None:
        payload["pending_state"] = pending_state
    if action is not None:
        payload["action"] = action
    if value is not None:
        payload["value"] = value

    t0 = time.time()
    try:
        r = requests.post(f"{API_URL}/api/chat/stream", json=payload, headers=headers, timeout=25, stream=True)
    except Exception as e:
        return {"error": str(e), "wall_ms": (time.time() - t0) * 1000, "parse_ms": 0, "tool_ms": 0, "verify_ms": 0, "llm_calls": 0, "cache": "error", "reply": str(e), "clarify": {}, "done": {}}

    events = []
    current_event = None

    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            raw_data = line[len("data:"):].strip()
            try:
                data = json.loads(raw_data)
            except Exception:
                data = {"raw": raw_data}
            events.append((current_event, data))

    total_wall_ms = round((time.time() - t0) * 1000, 2)

    done_data = next((d for ev, d in events if ev == "done"), {})
    ans_data = next((d for ev, d in events if ev == "answer"), {})
    clarify_data = next((d for ev, d in events if ev == "clarify"), {})
    debug_data = done_data.get("debug") or ans_data.get("debug") or clarify_data.get("debug") or {}
    timings = done_data.get("timings_ms", {})

    reply_preview = ans_data.get("markdown") or clarify_data.get("question") or ""
    if not reply_preview and "error" in done_data:
        reply_preview = f"ERROR: {done_data['error']}"

    tool_durations = [t.get("duration_ms", 0) for t in timings.get("tool_calls", [])]
    tool_ms = sum(tool_durations) if tool_durations else 0.0

    return {
        "wall_ms": total_wall_ms,
        "parse_ms": timings.get("parse_ms", 0.0),
        "tool_ms": tool_ms,
        "verify_ms": timings.get("verify_ms", 0.0),
        "llm_calls": timings.get("llm_calls_count", 0),
        "cache": debug_data.get("cache", "miss"),
        "cache_key": debug_data.get("cache_key", ""),
        "reply": reply_preview,
        "clarify": clarify_data,
        "done": done_data,
        "events": [ev for ev, _ in events]
    }

def main():
    scenarios = [
        ("1", "hello", "hello"),
        ("2", "standings 2026 drivers", "standings 2026 drivers"),
        ("3", "hamilton tire strategies", "hamilton tire strategies"),
        ("4", "alonso race strategies", "alonso race strategies"),
        ("6", "Who won Monza 2023?", "Who won Monza 2023?"),
        ("7", "leclercrrace strategyy", "leclercrrace strategyy"),
        ("8", "pit stops bahrain 2024", "pit stops bahrain 2024"),
    ]

    rows = []
    for num, label, msg in scenarios:
        res = send_chat(msg, client_id=f"step0-{num}")
        p_ms = res["parse_ms"]
        t_ms = res["tool_ms"]
        v_ms = res["verify_ms"]
        w_ms = res["wall_ms"]
        llm = res["llm_calls"]
        c = res["cache"]
        reply = res["reply"].replace("\n", " ")[:65]

        # Determine slowest step
        if p_ms >= t_ms and p_ms >= v_ms:
            slowest = "Parse"
        elif t_ms >= p_ms and t_ms >= v_ms:
            slowest = "Tools/Data"
        elif v_ms >= p_ms and v_ms >= t_ms:
            slowest = "Verify"
        else:
            slowest = "Network/SSE"

        rows.append((num, label, w_ms, p_ms, t_ms, llm, c, slowest, reply))

    # Multi-turn scenario 5
    cid5 = "step0-5-multiturn"
    r5_1 = send_chat("alonso race strategy", client_id=cid5)
    p1 = r5_1["clarify"].get("pending_state")
    r5_2 = send_chat("2023", client_id=cid5, pending_state=p1)
    p2 = r5_2["clarify"].get("pending_state")
    r5_3 = send_chat("More races", client_id=cid5, pending_state=p2)

    rep1 = r5_1["reply"].replace("\n", " ")[:20]
    rep2 = r5_2["reply"].replace("\n", " ")[:20]
    rep3 = r5_3["reply"].replace("\n", " ")[:25]
    s5_reply = f"T1: {rep1} | T2: {rep2} | T3: {rep3}"

    rows.insert(4, (
        "5",
        "alonso race strategy -> 2023 -> More races",
        round(r5_1["wall_ms"] + r5_2["wall_ms"] + r5_3["wall_ms"], 1),
        round(r5_1["parse_ms"] + r5_2["parse_ms"] + r5_3["parse_ms"], 1),
        round(r5_1["tool_ms"] + r5_2["tool_ms"] + r5_3["tool_ms"], 1),
        0,
        f"{r5_1['cache']}/{r5_2['cache']}/{r5_3['cache']}",
        "Parse (T3 drops)",
        s5_reply
    ))

    print("| # | Query / Scenario | Total ms | Parse ms | Tool ms | LLM Calls | Cache | Slowest Step | First Reply Preview |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | `{r[1]}` | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[8]} |")

if __name__ == "__main__":
    main()
