import json
import time
import requests

QUESTIONS = [
    "Which circuit hosts the Belgian GP?",
    "Who won Monza 2023?",
    "Show standings 2026 drivers",
    "Explain the pit stops at Bahrain 2024",
    "Compare Norris and Piastri tyre degradation at Silverstone 2024",
]

API_URL = "http://127.0.0.1:8000/api/chat/stream"

def run_baseline():
    results = []
    print("=" * 80)
    print("MEASURING BASELINE PERFORMANCE ACROSS 5 QUESTIONS (FRESH CHAT)")
    print("=" * 80)

    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/5] Running: '{q}'...")
        payload = {
            "message": q,
            "history": []
        }
        t0 = time.time()
        try:
            resp = requests.post(API_URL, json=payload, timeout=120)
            wall_ms = round((time.time() - t0) * 1000, 2)
            if resp.status_code == 200:
                answer = ""
                done_data = {}
                for line in resp.text.split("\n"):
                    if line.startswith("data: "):
                        try:
                            d = json.loads(line[6:].strip())
                            if "markdown" in d:
                                answer = d["markdown"]
                            if "timings_ms" in d:
                                done_data = d
                        except Exception:
                            pass
                timings = done_data.get("timings_ms", {})
                res_entry = {
                    "question": q,
                    "status": 200,
                    "wall_ms": wall_ms,
                    "parse_ms": timings.get("parse_ms", 0.0),
                    "tool_calls_count": timings.get("tool_calls_count", 0),
                    "tool_calls": timings.get("tool_calls", []),
                    "llm_calls_count": timings.get("llm_calls_count", 0),
                    "llm_calls": timings.get("llm_calls", []),
                    "verify_ms": timings.get("verify_ms", 0.0),
                    "total_ms": timings.get("total_ms", wall_ms),
                    "answer_preview": answer[:120].replace("\n", " "),
                }
                print(f" -> Done in {wall_ms}ms (Total reported: {res_entry['total_ms']}ms, Tools: {res_entry['tool_calls_count']}, LLM calls: {res_entry['llm_calls_count']})")
                results.append(res_entry)
            else:
                print(f" -> Error {resp.status_code}: {resp.text}")
                results.append({
                    "question": q,
                    "status": resp.status_code,
                    "wall_ms": wall_ms,
                    "error": resp.text
                })
        except Exception as e:
            wall_ms = round((time.time() - t0) * 1000, 2)
            print(f" -> Exception: {e}")
            results.append({
                "question": q,
                "status": "exception",
                "wall_ms": wall_ms,
                "error": str(e)
            })

    print("\n" + "=" * 80)
    print("BASELINE TIMING TABLE")
    print("=" * 80)
    header = f"{'Question':<45} | {'Parse':<8} | {'Tools (calls)':<14} | {'LLM (calls)':<12} | {'Verify':<8} | {'Total (ms)':<10}"
    print(header)
    print("-" * len(header))
    for r in results:
        if r.get("status") == 200:
            tool_summary = f"{r['tool_calls_count']} calls"
            llm_summary = f"{r['llm_calls_count']} calls"
            print(f"{r['question'][:43]:<45} | {r['parse_ms']:<8.1f} | {tool_summary:<14} | {llm_summary:<12} | {r['verify_ms']:<8.1f} | {r['total_ms']:<10.1f}")
        else:
            print(f"{r['question'][:43]:<45} | ERROR: {r.get('error', 'unknown')}")

    print("\n" + "=" * 80)
    print("DETAILED TOOL & LLM BREAKDOWN PER QUESTION")
    print("=" * 80)
    for r in results:
        if r.get("status") == 200:
            print(f"\nQuestion: \"{r['question']}\"")
            print(f"  Answer preview: {r['answer_preview']}...")
            print(f"  Parse: {r['parse_ms']} ms")
            print(f"  Verify: {r['verify_ms']} ms")
            print(f"  Total: {r['total_ms']} ms (Wall: {r['wall_ms']} ms)")
            print(f"  Tool calls ({len(r['tool_calls'])}):")
            for tc in r["tool_calls"]:
                print(f"    - {tc.get('name')}: {tc.get('duration_ms')} ms (cache: {tc.get('cache')})")
            print(f"  LLM calls ({len(r['llm_calls'])}):")
            for lc in r["llm_calls"]:
                print(f"    - {lc.get('provider')}: {lc.get('duration_ms')} ms")

    with open("tests/baseline_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved baseline results to tests/baseline_results.json")

if __name__ == "__main__":
    run_baseline()
