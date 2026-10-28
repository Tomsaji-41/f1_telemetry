import sys
import os
import json
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend import agent, config

def run_eval():
    config.validate()
    golden_path = BASE_DIR / "tests" / "golden_questions.json"
    with open(golden_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total = len(questions)
    factual_count = 0
    factual_tool_used = 0
    verified_count = 0
    refusal_correct = 0
    refusal_total = 0
    total_unsupported_numbers = 0
    latencies = []

    print(f"\n========================================================")
    print(f"RUNNING AI PITBOSS EVALUATION: {total} GOLDEN QUESTIONS")
    print(f"========================================================\n")

    for i, item in enumerate(questions, 1):
        q_id = item["id"]
        q_text = item["question"]
        q_type = item["type"]
        expected_fact = item["expected_fact"]

        t0 = time.time()
        try:
            res = agent.answer(q_text)
            latency = time.time() - t0
            latencies.append(latency)

            answer = res.get("answer", "")
            verified = res.get("verified", False)
            unsupported = res.get("unsupported_numbers", [])
            tool_calls = res.get("tool_calls_count", 0)

            total_unsupported_numbers += len(unsupported)
            if verified:
                verified_count += 1

            if q_type == "factual":
                factual_count += 1
                if tool_calls > 0:
                    factual_tool_used += 1
            else:
                refusal_total += 1
                # Check for correct refusal / limit statement / ambiguity
                lower_ans = answer.lower()
                is_correct_refusal = False
                if q_type == "unavailable" and any(k in lower_ans for k in ["not available", "not happened", "has not taken place", "no data", "cannot find"]):
                    is_correct_refusal = True
                elif q_type == "honest_limit" and any(k in lower_ans for k in ["2018", "2012", "only available", "not available"]):
                    is_correct_refusal = True
                elif q_type == "ambiguous" and any(k in lower_ans for k in ["which", "mean", "ambiguous", "candidate"]):
                    is_correct_refusal = True
                
                if is_correct_refusal:
                    refusal_correct += 1

            status_icon = "✓" if (verified and len(unsupported) == 0) else "✗"
            print(f"[{i:02d}/{total}] {status_icon} ({latency:.2f}s) {q_id}: {q_text[:50]}...")
            if unsupported:
                print(f"     WARNING: Unsupported numbers detected: {unsupported}")

            time.sleep(1.0)  # Gentle rate limit pacing

        except Exception as e:
            print(f"[{i:02d}/{total}] ✗ ERROR on {q_id}: {e}")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    tool_use_rate = (factual_tool_used / factual_count * 100) if factual_count else 100.0
    verified_rate = (verified_count / total * 100) if total else 0.0
    refusal_rate = (refusal_correct / refusal_total * 100) if refusal_total else 100.0

    print("\n" + "=" * 60)
    print("AI PITBOSS GROUNDING EVALUATION REPORT")
    print("=" * 60)
    print(f"Total Questions Evaluated:        {total}")
    print(f"Factual Tool-Use Rate:            {tool_use_rate:.1f}% (Target: 100%)")
    print(f"Verified Grounded Rate:           {verified_rate:.1f}% (Target: >= 95%)")
    print(f"Refusal/Limits Correctness:       {refusal_rate:.1f}%")
    print(f"Total Hallucinated Numbers:       {total_unsupported_numbers} (Must be 0)")
    print(f"Average Answer Latency:           {avg_latency:.2f}s")
    print("=" * 60)

    # Assertions
    failed = False
    if total_unsupported_numbers > 0:
        print("FAIL: Hallucinated numbers detected!")
        failed = True
    if tool_use_rate < 100.0:
        print("FAIL: Tool-use rate on factual questions fell below 100%!")
        failed = True
    if verified_rate < 95.0:
        print(f"FAIL: Verified rate ({verified_rate:.1f}%) is below 95% target!")
        failed = True

    if failed:
        sys.exit(1)
    else:
        print("PASS: ALL ACCURACY AND GROUNDING CRITERIA MET!")
        sys.exit(0)

if __name__ == "__main__":
    run_eval()
