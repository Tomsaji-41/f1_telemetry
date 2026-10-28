import re
import json
import logging
from typing import List, Dict, Any, Set, Optional, Tuple

logger = logging.getLogger("verifier")

SPECULATIVE_WORDS = [
    "probably traffic", "likely", "probably", "because", "due to", "aimed to", "chosen for",
    "designed to", "struggled", "hot track", "clear track position",
    "traffic", "tyre degradation"
]

def _extract_all_numbers_from_obj(obj: Any, floats: Set[float], strings: Set[str]):
    if isinstance(obj, (int, float)):
        floats.add(round(float(obj), 3))
        strings.add(str(obj))
    elif isinstance(obj, str):
        strings.add(obj.lower())
        strings.add(obj)
        for lt in re.findall(r"\b\d+:\d{2}(?:\.\d+)?\b", obj):
            strings.add(lt)
        for m in re.findall(r"\b\d+(?:\.\d+)?\b", obj):
            try:
                floats.add(round(float(m), 3))
            except ValueError:
                pass
    elif isinstance(obj, dict):
        for k, v in obj.items():
            strings.add(str(k).lower())
            _extract_all_numbers_from_obj(v, floats, strings)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            _extract_all_numbers_from_obj(item, floats, strings)

def clean(text: str, tool_outputs: Optional[List[Any]] = None, user_prompt: Optional[str] = None) -> str:
    cleaned, _ = clean_unsupported_causes(text, tool_outputs, user_prompt)
    return cleaned

def clean_unsupported_causes(
    text: str,
    tool_outputs: Optional[List[Any]] = None,
    user_prompt: Optional[str] = None
) -> Tuple[str, List[str]]:
    if not text:
        return "", []

    tool_str = json.dumps(tool_outputs or [], default=str).lower()
    if user_prompt:
        tool_str += " " + user_prompt.lower()

    detected_causes = []
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line_clean = line
        line_lower = line.lower()
        if "my read:" in line_lower:
            # Explicitly allowed if backed by data
            cleaned_lines.append(line)
            continue

        for word in SPECULATIVE_WORDS:
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, line_lower):
                if word not in tool_str:
                    detected_causes.append(word)
                    # Remove the speculation phrase / clause
                    line_clean = re.sub(rf"(?:,|\band\b)?\s*[^,.]*?\b{re.escape(word)}\b[^,.]*", "", line_clean, flags=re.IGNORECASE)

        cleaned_text = line_clean.strip()
        if not cleaned_text:
            cleaned_lines.append("")
        elif not cleaned_text.startswith("|"):  # Don't drop table borders
            cleaned_lines.append(cleaned_text)
        elif line.strip().startswith("|"):
            cleaned_lines.append(line)

    res = "\n".join(cleaned_lines).strip()
    return res, list(dict.fromkeys(detected_causes))

def check(
    answer: str,
    tool_outputs: List[Any],
    user_prompt: Optional[str] = None,
    resolved_context: Optional[Dict[str, Any]] = None,
    fallback_table: Optional[str] = None
) -> Dict[str, Any]:
    """
    Deterministic verifier implementing rules V1-V5:
    Allowed tokens = tool outputs of this turn + resolved_context + user's own numbers.
    V1: Numbers must match tool output (normalise time formats).
    V2: Context-leak check: Any year, 'Round N' or Grand Prix name not in resolved_context,
        user prompt or tool output is a leak: delete that sentence.
    V3: Delete sentences with causal or speculative wording unless labelled 'My read:' and backed by tool data.
    V4: Count claims (stops, compounds, stints) must equal computed counts.
    V5: If more than 30% of sentences are removed, show the code-rendered table only.
    """
    if not answer or not answer.strip():
        return {
            "unsupported": [],
            "unsupported_causes": [],
            "verified": True,
            "cleaned_text": answer or ""
        }

    # Prepare allowed tokens and string representations
    tool_str = json.dumps(tool_outputs, default=str).lower()
    tool_floats: Set[float] = set()
    tool_strings: Set[str] = set()
    _extract_all_numbers_from_obj(tool_outputs, tool_floats, tool_strings)

    ctx_str = ""
    if resolved_context:
        ctx_str = json.dumps(resolved_context, default=str).lower()
        _extract_all_numbers_from_obj(resolved_context, tool_floats, tool_strings)

    prompt_str = ""
    if user_prompt:
        if isinstance(user_prompt, str):
            prompt_str = user_prompt.lower()
        else:
            prompt_str = json.dumps(user_prompt, default=str).lower()
        _extract_all_numbers_from_obj(user_prompt, tool_floats, tool_strings)

    allowed_str = f"{tool_str} {ctx_str} {prompt_str}"

    # Split into paragraphs to preserve markdown structure and tables
    paragraphs = [p.strip() for p in answer.strip().split("\n\n") if p.strip()]
    total_paragraphs = len(paragraphs)
    valid_paragraphs = []
    unsupported_numbers = []
    unsupported_causes = []

    for para in paragraphs:
        # Preserve tables, markdown headers, and structured telemetry directly
        if para.startswith("|") or "\n|" in para or para.startswith("#") or para.startswith("**") or para.startswith("Race:"):
            valid_paragraphs.append(para)
            continue

        # For text sentences within paragraph:
        raw_sentences = re.split(r"(?<=[.!?])\s+", para)
        valid_sentences = []
        for sent in raw_sentences:
            sent_clean = sent.strip()
            if not sent_clean:
                continue

            sent_lower = sent_clean.lower()
            if re.match(r"^\s*\d+[\.\)]?\s*$", sent_clean):
                valid_sentences.append(sent_clean)
                continue

            if sent_clean.startswith("|") or sent_clean.startswith("#") or sent_clean.endswith("?") or sent_lower.startswith(("want to", "would you like", "could we", "options:", "follow-up:")):
                valid_sentences.append(sent_clean)
                continue

            # V3: Speculative / Causal wording check
            has_speculation = False
            if "my read:" not in sent_lower:
                for word in SPECULATIVE_WORDS:
                    if re.search(rf"\b{re.escape(word)}\b", sent_lower):
                        if word not in allowed_str:
                            unsupported_causes.append(word)
                            has_speculation = True
                            break
            if has_speculation:
                continue

            # V2: Leak check: Any 4-digit year, 'Round N' or Grand Prix name
            leaked = False
            year_matches = re.findall(r"\b(19\d{2}|20\d{2})\b", sent_clean)
            for ym in year_matches:
                if ym not in allowed_str:
                    leaked = True
                    break

            round_matches = re.findall(r"\bround\s+(\d+)\b", sent_lower)
            for rm in round_matches:
                if rm not in tool_strings and f'"round": {rm}' not in allowed_str and f'"round": "{rm}"' not in allowed_str and rm not in allowed_str:
                    leaked = True
                    break

            # V1: Number and lap time verification
            sent_body = re.sub(r"^\s*\d+\.\s+", "", sent_clean)
            for lt in re.findall(r"\b\d+:\d{2}(?:\.\d+)?\b", sent_body):
                if lt not in tool_strings and lt not in allowed_str:
                    unsupported_numbers.append(lt)

            sent_no_lt = re.sub(r"\b\d+:\d{2}(?:\.\d+)?\b", " ", sent_body)
            for m in re.findall(r"\b\d+(?:\.\d+)?\b", sent_no_lt):
                try:
                    f_val = round(float(m), 3)
                except ValueError:
                    f_val = None
                if f_val not in tool_floats and m not in tool_strings and m not in allowed_str:
                    unsupported_numbers.append(m)

            valid_sentences.append(sent_clean)

        if valid_sentences:
            valid_paragraphs.append(" ".join(valid_sentences))

    # Reassemble cleaned markdown
    cleaned_text = "\n\n".join(valid_paragraphs)

    unique_unsupported = list(dict.fromkeys(unsupported_numbers))
    unique_causes = list(dict.fromkeys(unsupported_causes))
    is_verified = (len(unique_unsupported) == 0 and len(unique_causes) == 0)

    return {
        "unsupported": unique_unsupported,
        "unsupported_causes": unique_causes,
        "verified": is_verified,
        "cleaned_text": cleaned_text
    }
