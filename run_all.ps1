# AI Pitboss - Dual Server Launcher (FastAPI Backend + Next.js Frontend)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting AI Pitboss: Backend (FastAPI) and Frontend (Next.js)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Start Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000 --reload"

Start-Sleep -Seconds 2

# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location frontend; npm run dev"

Write-Host ""
Write-Host "Both servers are launching!" -ForegroundColor Green
Write-Host "Backend API & Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "Frontend Dashboard: http://localhost:3000" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
