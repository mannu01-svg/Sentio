@echo off
rem ---------------------------------------------------------------------------
rem Sentio - start the whole stack in Docker (Windows).
rem
rem   Double-click start.bat, or from a terminal:
rem     startup\windows\start.bat            full mode (VADER + DistilBERT + RoBERTa)
rem     startup\windows\start.bat --fast     VADER only (lighter, quicker demo)
rem     startup\windows\start.bat --fresh    wipe all data first (clean demo state)
rem
rem Only prerequisite: Docker Desktop, running. Python/Java/Node are NOT needed
rem on Windows any more - everything runs inside containers.
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0..\.."

set "FRESH="
for %%a in (%*) do (
  if /i "%%a"=="--fast" set "SKIP_BERT=1"
  if /i "%%a"=="--fresh" set "FRESH=1"
)

echo ===============================================
echo  Sentio - starting in Docker
echo ===============================================

where docker >nul 2>nul || (echo [X] Docker not found - install Docker Desktop: https://www.docker.com/products/docker-desktop/ & pause & exit /b 1)
docker info >nul 2>nul || (echo [X] Docker Desktop is not running - start it and wait for "Engine running" & pause & exit /b 1)

if defined FRESH (
  echo [*] --fresh: removing containers and all stored data...
  docker compose down -v
)
if defined SKIP_BERT echo [*] --fast: VADER only, transformer models skipped

echo [1/3] Building and starting containers. First run downloads ~4 GB and takes 15-25 min...
docker compose up -d --build
if errorlevel 1 (echo [X] docker compose failed - see the messages above & pause & exit /b 1)

echo [2/3] Waiting for the API...
set /a tries=0
:wait
set /a tries+=1
curl -fs http://localhost:8000/health >nul 2>nul && goto ready
if %tries% geq 60 goto notready
timeout /t 5 /nobreak >nul
goto wait

:notready
echo [!] The API is not answering yet - check: docker compose logs api
goto summary

:ready
echo       API is up

:summary
echo [3/3] Containers:
docker compose ps
echo.
echo ===============================================
echo   Dashboard : http://localhost:5173   (admin@sentio.app / admin123)
echo   Swagger   : http://localhost:8000/docs
echo   Spark UI  : http://localhost:4040
echo   MongoDB   : mongodb://localhost:27017   (database: sentio)
echo.
echo   Spark log : docker compose logs -f spark
echo   Stop      : startup\windows\stop.bat
echo ===============================================
start "" http://localhost:5173
pause
