import json

log_path = r"C:\Users\user\.gemini\antigravity-ide\brain\b5e67e2e-1c1d-4f09-b09e-bec3fea60eec\.system_generated\logs\transcript_full.jsonl"
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("step_index") == 327:
            with open("v7_requirements.txt", "w", encoding="utf-8") as out:
                out.write(data.get("content", ""))
            print("Wrote v7_requirements.txt, length:", len(data.get("content", "")))
            break
