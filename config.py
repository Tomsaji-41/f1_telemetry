import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

def _clean(v):
    v = (v or "").strip()
    return "" if v.startswith("<") else v

CACHE_DIR = BASE_DIR / "f1_cache"
DATA_DIR = BASE_DIR / "data"

CACHE_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# API Keys loaded directly from environment variables via .env
GEMINI_API_KEY = _clean(os.getenv("GEMINI_API_KEY"))
GROQ_API_KEY = _clean(os.getenv("GROQ_API_KEY"))
FASTF1_CACHE_DIR = os.getenv("FASTF1_CACHE_DIR", str(CACHE_DIR))

# Model configurations
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_FIRST_TOKEN_TIMEOUT_S = float(os.getenv("GEMINI_FIRST_TOKEN_TIMEOUT_S", "3"))
GEMINI_TOTAL_TIMEOUT_S = float(os.getenv("GEMINI_TOTAL_TIMEOUT_S", "8"))

def mask_key(k: str) -> str:
    """Mask key in log outputs, showing only the first 4 characters."""
    if not k:
        return ""
    return k[:4] + "*" * min(8, max(0, len(k) - 4))

# Seasons range automatically configured up to 2026
SUPPORTED_SEASONS = list(range(2018, 2027))
DEFAULT_SEASON_RANGE = SUPPORTED_SEASONS
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8000))
