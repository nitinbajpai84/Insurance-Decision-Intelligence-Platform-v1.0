@echo off
REM Anchor to this script's directory so relative paths resolve correctly.
cd /d "%~dp0"

echo === Starting Insurance PoC V2.0 ===
call venv\Scripts\activate

echo Starting V2 backend on port 3001...
REM NOTE: --reload was removed. watchfiles isn't installed in this venv, so uvicorn
REM falls back to StatReload, which does a full recursive *.py scan of the ENTIRE
REM project root (both venv/.venv site-packages trees, frontend_v2/node_modules,
REM data/) every ~0.25-1s. That constant scan burns escalating CPU (measured 200s+
REM CPU time within ~10 minutes) and is the most likely cause of the backend going
REM unresponsive/crashing during a demo. For live code-reload during development,
REM run manually with a scoped reload dir instead, e.g.:
REM   uvicorn backend_v2.api.main:app --port 3001 --reload --reload-dir backend_v2 --reload-dir graph
start "V2 Backend" cmd /k "python -m uvicorn backend_v2.api.main:app --port 3001"

timeout /t 3

echo Starting V2 frontend on port 3002...
start "V2 Frontend" cmd /k "cd frontend_v2 && npm install && npm run dev -- --port 3002"

timeout /t 5
echo Opening browser...
start http://127.0.0.1:3002

echo.
echo V1 still running on: http://127.0.0.1:3000
echo V2 now running on:   http://127.0.0.1:3002
echo V2 API running on:   http://127.0.0.1:3001
