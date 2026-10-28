import json
import re
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import parser, state

client = TestClient(app)

DATA_DIR = Path(__file__).resolve().parent / "data"

def test_nlu():
    cases_file = DATA_DIR / "nlu_cases.jsonl"
    assert cases_file.exists(), f"Missing {cases_file}"

    cases = [json.loads(line) for line in cases_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(cases) > 0

    intent_passed = 0
    slot_passed = 0
    missing_passed = 0
    total = len(cases)

    errors = []

    for idx, c in enumerate(cases):
        text = c["text"]
        exp_intent = c["intent"]
        exp_slots = c["slots"]
        exp_missing = c["missing"]

        det_intent, _ = parser.detect_intent(text)
        det_slots = parser.extract_slots(text, det_intent)
        det_missing = parser.get_missing_slots(det_intent, det_slots, text)

        if det_intent == exp_intent:
            intent_passed += 1
        else:
            errors.append(f"Case {idx+1} '{text}': expected intent {exp_intent}, got {det_intent}")

        if det_slots == exp_slots:
            slot_passed += 1
        else:
            errors.append(f"Case {idx+1} '{text}': expected slots {exp_slots}, got {det_slots}")

        if det_missing == exp_missing:
            missing_passed += 1
        else:
            errors.append(f"Case {idx+1} '{text}': expected missing {exp_missing}, got {det_missing}")

    print(f"\n[NLU EVALUATION] Intent Accuracy: {intent_passed}/{total} ({intent_passed/total*100:.1f}%), Slot Accuracy: {slot_passed}/{total} ({slot_passed/total*100:.1f}%), Missing Accuracy: {missing_passed}/{total} ({missing_passed/total*100:.1f}%)")

    assert intent_passed == total, f"NLU Intent errors:\n" + "\n".join(errors)
    assert slot_passed == total, f"NLU Slot errors:\n" + "\n".join(errors)
    assert missing_passed == total, f"NLU Missing errors:\n" + "\n".join(errors)

def test_flows():
    flows_file = DATA_DIR / "flow_cases.json"
    assert flows_file.exists(), f"Missing {flows_file}"

    flows = json.loads(flows_file.read_text(encoding="utf-8"))
    assert len(flows) > 0

    passed_flows = 0

    for flow in flows:
        flow_name = flow["name"]
        conv_id = f"flow_{flow_name}"
        state.save_conv_state(conv_id, f"client_{conv_id}", {"pending": None, "last_race": None, "greeted": False})
        steps = flow["steps"]
        last_options = []

        print(f"\n--- Running flow: {flow_name} ---")

        for s_idx, step in enumerate(steps):
            send_payload = dict(step["send"])
            expect = step.get("expect", {})

            # Prepare request body
            body = {"conversation_id": conv_id}

            if "text" in send_payload:
                body["text"] = send_payload["text"]
            else:
                body["action"] = send_payload.get("action")
                if "value" in send_payload:
                    body["value"] = send_payload["value"]

                if "option_label" in send_payload:
                    target_label = send_payload["option_label"]
                    body["option_label"] = target_label
                    # Pick from last_options if possible
                    matched_opt = next((o for o in last_options if o.get("label") == target_label), None)
                    if matched_opt:
                        body["value"] = matched_opt.get("value")
                elif "option_index" in send_payload:
                    idx = send_payload["option_index"]
                    body["option_index"] = idx
                    if 0 <= idx < len(last_options):
                        body["value"] = last_options[idx].get("value")
                        body["option_label"] = last_options[idx].get("label")

            resp = client.post("/api/chat", json=body, headers={"X-Client-Id": f"client_{conv_id}"})
            assert resp.status_code == 200, f"Flow '{flow_name}' step {s_idx+1} failed with status {resp.status_code}: {resp.text}"

            data = resp.json()
            resp_text = json.dumps(data)

            # User visible text in UI: question, progress, markdown, option labels
            user_visible_text = f"{data.get('question', '')} {data.get('progress', '')} {data.get('markdown', '')} {' '.join(o.get('label', '') for o in data.get('options', []))}"

            # Global forbidden checks for flow (Section 5.2 & B2)
            assert "MORE_RACES" not in user_visible_text, f"Flow '{flow_name}' step {s_idx+1} contained forbidden token 'MORE_RACES' in UI: {user_visible_text}"
            assert "grand_prix" not in user_visible_text.lower(), f"Flow '{flow_name}' step {s_idx+1} contained forbidden token 'grand_prix' in UI: {user_visible_text}"
            assert "engine" not in user_visible_text, f"Flow '{flow_name}' step {s_idx+1} contained stray label 'engine'"

            if expect.get("no_welcome"):
                assert "Welcome to AI Pitboss" not in user_visible_text, f"Flow '{flow_name}' step {s_idx+1} contained welcome message when forbidden"

            # Check specific expectations
            if "type" in expect:
                assert data.get("type") == expect["type"], f"Flow '{flow_name}' step {s_idx+1} expected type {expect['type']}, got {data.get('type')}: {resp_text}"

            if "awaiting" in expect:
                assert data.get("awaiting") == expect["awaiting"], f"Flow '{flow_name}' step {s_idx+1} expected awaiting {expect['awaiting']}, got {data.get('awaiting')}"

            if "header_contains" in expect:
                markdown = data.get("markdown", "")
                assert expect["header_contains"] in markdown, f"Flow '{flow_name}' step {s_idx+1} markdown missing header '{expect['header_contains']}': {markdown}"

            if "answer_intent" in expect:
                assert data.get("answer_intent") == expect["answer_intent"], f"Flow '{flow_name}' step {s_idx+1} expected answer_intent {expect['answer_intent']}, got {data.get('answer_intent')}"

            if "options_min" in expect:
                options = data.get("options", [])
                assert len(options) >= expect["options_min"], f"Flow '{flow_name}' step {s_idx+1} expected >= {expect['options_min']} options, got {len(options)}"

            if "options_labels_contain" in expect:
                options = data.get("options", [])
                opt_labels = [o.get("label", "") for o in options]
                for exp_lbl in expect["options_labels_contain"]:
                    assert any(exp_lbl in l for l in opt_labels), f"Flow '{flow_name}' step {s_idx+1} options {opt_labels} missing '{exp_lbl}'"

            if "forbid" in expect:
                for f_str in expect["forbid"]:
                    assert f_str not in user_visible_text, f"Flow '{flow_name}' step {s_idx+1} contained forbidden string '{f_str}' in UI: {user_visible_text}"

            # Update last_options
            if data.get("options"):
                last_options = data["options"]
            elif data.get("followups"):
                last_options = data["followups"]

        passed_flows += 1

    print(f"\n[FLOW EVALUATION] Passed {passed_flows}/{len(flows)} flows (100%)")
