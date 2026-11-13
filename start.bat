# ---------------------------------------------------------------------------
# One command to run the entire Sentio pipeline on Windows.
#
#   Double-click start.bat   (or run it from any terminal)
#
# Everything is automatic: docker, bootstrap (python env, npm, JDK, model
# weights, demo user), spark, producer, api, dashboard. Just wait.
#
# Prerequisites (system apps — can't be auto-installed):
#   Docker Desktop (running)  https://www.docker.com/products/docker-desktop/
#   Node.js 18+               https://nodejs.org/
#   Python 3.10-3.12          https://www.python.org/downloads/ (check "Add to PATH")
#
# Requires Windows 10+ with WSL2 enabled for Spark (Docker Desktop with
# WSL2 backend covers this).
# ---------------------------------------------------------------------------
@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
set ROOT=%cd%

echo ===============================================
echo  Sentio - one-command setup (Windows)
echo ===============================================

where docker >nul 2>nul || (echo [X] docker not found - install Docker Desktop and start it & pause & exit /b 1)
docker info >nul 2>nul || (echo [X] docker daemon not running - start Docker Desktop first & pause & exit /b 1)
where node >nul 2>nul || (echo [X] node.js not found - install node 18+ from nodejs.org & pause & exit /b 1)
where python >nul 2>nul || (echo [X] python not found - install python 3.10-3.12 from python.org, check "Add to PATH" & pause & exit /b 1)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [1/7] first run: creating python env + installing packages ~3-5 min...
  python -m venv .venv || (echo [X] venv failed & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\pip.exe" install --quiet -r requirements.txt || (echo [X] pip install failed & pause & exit /b 1)
  echo       python env ready
) else (
  echo [1/7] python env already present
)

if not exist "%ROOT%\frontend\node_modules" (
  echo [2/7] npm install ~1-2 min...
  pushd frontend
  call npm install --no-audit --no-fund || (echo [X] npm install failed & popd & pause & exit /b 1)
  popd
  echo       frontend deps ready
) else (
  echo [2/7] node_modules already present
)

echo [3/7] starting kafka + postgres containers...
docker rm -f sma-kafka sma-postgres >nul 2>nul
docker compose up -d || (echo [X] docker compose failed & pause & exit /b 1)

echo       waiting for containers to be healthy...
set /a tries=0
:waitloop
set /a tries+=1
docker inspect -f "{{.State.Health.Status}}" sma-kafka 2>nul | findstr healthy >nul && docker inspect -f "{{.State.Health.Status}}" sma-postgres 2>nul | findstr healthy >nul && goto healthy
if %tries% geq 90 (echo [X] containers not healthy - run: docker compose logs & pause & exit /b 1)
timeout /t 2 /nobreak >nul
goto waitloop
:healthy
echo       kafka + postgres healthy

echo [4/7] kafka topics...
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-raw --partitions 3 --if-not-exists >nul 2>nul
docker exec sma-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --create --topic comments-scored --partitions 3 --if-not-exists >nul 2>nul

echo [5/7] model warmup (one-time HF download ~5 min, skipped if cached)...
if not exist "%USERPROFILE%\.cache\huggingface\hub\models--cardiffnlp--twitter-roberta-base-sentiment-latest" (
  ".venv\Scripts\python.exe" scripts\warmup_models.py || echo       warmup failed - spark will retry on start
) else (
  echo       sentiment models already cached
)

echo [6/7] demo user...
".venv\Scripts\python.exe" scripts\seed_demo_user.py

echo [7/7] starting services (separate windows)...
if not exist logs mkdir logs

start "sentio-spark" /min cmd /c "run_spark.bat > logs\spark.log 2>&1"
start "sentio-producer" /min cmd /c '".venv\Scripts\python.exe" producer\producer.py --file data\raw\all_sources.csv --seed 6000 --shuffle > logs\producer.log 2>&1'
start "sentio-api" /min cmd /c '".venv\Scripts\python.exe" -m uvicorn api.main:app --port 8000 > logs\api.log 2>&1'
start "sentio-frontend" /min cmd /c "cd frontend && npm run dev > ..\logs\frontend.log 2>&1"

echo       waiting for the API (~45 s)...
timeout /t 45 /nobreak >nul

echo ===============================================
echo.
echo   Dashboard:    http://localhost:5173
echo   Login:        ada@sentio.app / secret123
echo   API docs:     http://localhost:8000/docs
echo   Spark UI:     http://localhost:4040
echo.
echo   Logs:         logs\spark.log producer.log api.log frontend.log
echo   Stop all:     stop.bat
echo ===============================================
pause
