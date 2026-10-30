# AI Pitboss - Dual Server Launcher (FastAPI Backend + Next.js Frontend)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting AI Pitboss: Backend (FastAPI) and Frontend (Next.js)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start Backend
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$RootDir'; & .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend --reload-exclude 'f1_cache' --reload-exclude '*.sqlite*' --reload-exclude 'data' --reload-exclude 'logs'"

Start-Sleep -Seconds 2

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$RootDir\frontend'; npm run dev"

Write-Host ""
Write-Host "Both servers are launching!" -ForegroundColor Green
Write-Host "Backend API & Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "Frontend Dashboard: http://localhost:3000" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
