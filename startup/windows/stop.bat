@echo off
rem Sentio - stop every container (stored data is kept; use start.bat --fresh to wipe it).
cd /d "%~dp0..\.."
docker compose down
echo stopped (data kept in Docker volumes)
pause
