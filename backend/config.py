import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

def _clean(v):
    v = (v or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1].strip()
    return "" if v.startswith("<") else v

GEMINI_API_KEY = _clean(os.getenv("GEMINI_API_KEY"))
GROQ_API_KEY = _clean(os.getenv("GROQ_API_KEY"))
GEMINI_MODEL = _clean(os.getenv("GEMINI_MODEL", "gemini-2.5-flash")) or "gemini-2.5-flash"
GROQ_MODEL = _clean(os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")) or "llama-3.3-70b-versatile"
GEMINI_FIRST_TOKEN_TIMEOUT_S = float(os.getenv("GEMINI_FIRST_TOKEN_TIMEOUT_S", "3"))
GEMINI_TOTAL_TIMEOUT_S = float(os.getenv("GEMINI_TOTAL_TIMEOUT_S", "8"))

# Cache & data storage paths (outside watched backend source tree)
CACHE_DIR = Path(os.getenv("F1_CACHE_DIR", BASE_DIR / "f1_cache"))
CACHE_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("F1_DB_PATH", BASE_DIR / "cache.sqlite"))
DATA_DIR = Path(os.getenv("F1_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path(os.getenv("F1_LOGS_DIR", BASE_DIR / "logs"))
LOGS_DIR.mkdir(exist_ok=True)

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))

# Chart / telemetry constants (not F1 facts — pure model/config knobs)
MAX_POINTS        = 1500          # max scatter points returned per request
NEUTRAL_COLOUR    = "#A9A9BC"     # fallback when FastF1 plotting has no colour
FUEL_EFFECT_S_PER_LAP = 0.055    # model assumption for fuel-corrected deg; shown in UI
PIT_MIN_S         = 1.8          # below this → suspect (tyre change only, no stationary)
PIT_MAX_S         = 60.0         # above this → suspect (drive-through, VSC confusion)
DATA_DIR          = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def mask_key(k: str) -> str:
    """Mask key in log outputs, showing only the first 4 characters."""
    if not k:
        return ""
    return k[:4] + "*" * min(8, max(0, len(k) - 4))

def validate():
    if not (GEMINI_API_KEY or GROQ_API_KEY):
        print(f"[config WARNING] No LLM key found in .env at {BASE_DIR / '.env'}. Deterministic pipelines will function, but LLM fallbacks will be disabled.")
    else:
        print(f"[config] gemini={bool(GEMINI_API_KEY)} (masked: {mask_key(GEMINI_API_KEY)}) groq={bool(GROQ_API_KEY)} (masked: {mask_key(GROQ_API_KEY)})")

if __name__ == "__main__":
    validate()
