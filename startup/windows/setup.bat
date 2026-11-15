@echo off
rem ---------------------------------------------------------------------------
rem THE one command for a completely fresh clone:
rem
rem   Double-click setup.bat   (in startup\windows\)
rem
rem Does everything: python venv + pip, npm install, model weights rejoin,
rem HuggingFace LLM download, docker (Kafka + Postgres), all 4 services,
rem demo login user - then Jenkins CI (zero-click: admin user + sentio-ci
rem job + first build kicked off automatically).
rem ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
cd /d "%~dp0"
rem repo root: this script lives in startup\windows\ - the project root is two levels up
for %%i in ("%~dp0..\..") do set ROOT=%%~fi
cd /d "%ROOT%"

echo ===============================================
echo  Sentio - full setup (app + services + Jenkins)
echo ===============================================

rem 1. app + services (start.bat handles everything incl. fresh-clone bootstrap)
call "%~dp0start.bat"
if errorlevel 1 (echo [X] app setup failed - see messages above & pause & exit /b 1)

rem 2. Jenkins CI - zero-click (AUTO=1: admin sentio/sentio123, job created, build queued)
echo.
echo [CI] starting Jenkins...
set AUTO=1
set JENKINS_PORT=8090
bash run_jenkins.sh 2>nul
if errorlevel 1 (
  echo [!] bash not found - trying Git Bash / WSL fallback for Jenkins...
  where wsl >nul 2>nul && (wsl bash -c "cd /mnt/%ROOT:C:=c% && AUTO=1 JENKINS_PORT=8090 bash run_jenkins.sh") || (
    echo [X] could not run Jenkins setup - open a Git Bash prompt and run: AUTO=1 JENKINS_PORT=8090 bash run_jenkins.sh
  )
)

echo ===============================================
echo.
echo   Sentio is fully up:
echo.
echo   Dashboard : http://localhost:5173      ^(ada@sentio.app / secret123^)
echo   API docs  : http://localhost:8000/docs
echo   Jenkins   : http://localhost:8090      ^(sentio / sentio123^)
echo.
echo   Stop all  : stop.bat  +  docker rm -f sma-jenkins
echo ===============================================
pause
