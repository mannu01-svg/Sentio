# Windows: stop every Sentio service (containers kept; data intact).
@echo off
taskkill /fi "WINDOWTITLE eq sentio-spark*" /f >nul 2>nul
taskkill /fi "WINDOWTITLE eq sentio-producer*" /f >nul 2>nul
taskkill /fi "WINDOWTITLE eq sentio-api*" /f >nul 2>nul
taskkill /fi "WINDOWTITLE eq sentio-frontend*" /f >nul 2>nul
wmic process where "commandline like '%%streaming_job.py%%'" call terminate >nul 2>nul
wmic process where "commandline like '%%producer.py%%'" call terminate >nul 2>nul
wmic process where "commandline like '%%uvicorn api.main%%'" call terminate >nul 2>nul
echo stopped (kafka + postgres containers kept)
pause
