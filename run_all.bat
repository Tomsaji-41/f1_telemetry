@echo off
cd /d "%~dp0"
echo ========================================================
echo Starting AI Pitboss: Backend (FastAPI) and Frontend (Next.js)
echo ========================================================

start "Pitboss Backend [Port 8000]" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-exclude "f1_cache" --reload-exclude "*.sqlite*" --reload-exclude "data" --reload-exclude "logs""

timeout /t 2 /nobreak >nul

start "Pitboss Frontend [Port 3000]" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers are launching!
echo Backend API & Docs: http://127.0.0.1:8000/docs
echo Frontend Dashboard: http://localhost:3000
echo ========================================================
