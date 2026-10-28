import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

BANNED_STRINGS = [
    "1:29.825",
    "1:30.012",
    "Debris cleared",
    "PIT STOP WINDOW",
    "YELLOW FLAG Sector 3",
    "Honda RBPT",
    "AlphaTauri / VCARB",
    "Max Verstappen(VER)",
]

def get_source_files():
    """Collect Python, TypeScript, JavaScript, and TSX files outside tests/ and data/editorial/."""
    files = []
    
    # Backend
    backend_dir = REPO_ROOT / "backend"
    if backend_dir.exists():
        for p in backend_dir.rglob("*.py"):
            if "__pycache__" not in str(p):
                files.append(p)
                
    # Frontend src
    frontend_src = REPO_ROOT / "frontend" / "src"
    if frontend_src.exists():
        for ext in ("*.ts", "*.tsx", "*.js", "*.jsx"):
            for p in frontend_src.rglob(ext):
                if "__tests__" not in str(p) and "node_modules" not in str(p):
                    files.append(p)
                    
    return files

def test_no_banned_f1_strings():
    """Verify none of the purged F1 fact strings exist in frontend or backend source."""
    files = get_source_files()
    assert len(files) > 0, "No source files found to scan"
    
    violations = []
    for f in files:
        content = f.read_text(encoding="utf-8", errors="ignore")
        for banned in BANNED_STRINGS:
            if banned in content:
                violations.append(f"{f.relative_to(REPO_ROOT)}: contains banned string '{banned}'")
                
    assert not violations, "Found prohibited hardcoded F1 strings:\n" + "\n".join(violations)

def test_force_renew_only_in_auto_update():
    """Rule 2.3 & Test 11: force_renew appears only in auto_update.py."""
    files = get_source_files()
    violations = []
    for f in files:
        if f.name == "auto_update.py":
            continue
        content = f.read_text(encoding="utf-8", errors="ignore")
        if "force_renew" in content:
            violations.append(f"{f.relative_to(REPO_ROOT)} contains force_renew")
    assert not violations, "force_renew must only appear in backend/auto_update.py:\n" + "\n".join(violations)

def test_no_default_hardcoded_years():
    """Rule 5 & Test 5: Verify no four-digit year 1950..2100 is used as a default season in store or controls."""
    files = get_source_files()
    violations = []
    
    # Check for patterns like season: 2024, defaultYear = 2024, etc.
    year_default_pattern = re.compile(r'(?:defaultSeason|season\s*:\s*|defaultYear\s*=\s*)(19\d\d|20\d\d)\b')
    for f in files:
        # Ignore comments or purely historical era definition files
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            line_clean = line.strip()
            if line_clean.startswith("//") or line_clean.startswith("#"):
                continue
            m = year_default_pattern.search(line)
            if m:
                violations.append(f"{f.relative_to(REPO_ROOT)}:L{i}: {line_clean}")
                
    assert not violations, "Found hardcoded default year:\n" + "\n".join(violations)
