# Windows: run the Spark streaming job with Java 17 on PATH.
# Called by start.bat. Keeps the same env contract as run_spark.sh.
@echo off
rem repo root: this script lives in startup\windows\ — the project root is two levels up
cd /d "%~dp0..\.."
set "BATDIR=%~dp0"

if defined JAVA_HOME if exist "%JAVA_HOME%\bin\java.exe" goto run

rem prefer a user-local JDK downloaded by bootstrap, then system java
if exist "%USERPROFILE%\.tools\jdk-17\bin\java.exe" (
  set "JAVA_HOME=%USERPROFILE%\.tools\jdk-17"
  set "PATH=%JAVA_HOME%\bin;%PATH%"
  goto run
)
where java >nul 2>nul || (echo [X] java 17 not found - install from adoptium.net or let the bootstrap download it & exit /b 1)

:run
set PYTHONPATH=%cd%\spark;%PYTHONPATH%
set PYSPARK_PYTHON=%cd%\.venv\Scripts\python.exe
set PYSPARK_DRIVER_PYTHON=%cd%\.venv\Scripts\python.exe
set PYTHONUNBUFFERED=1
set NLP_TORCH_THREADS=4

"%cd%\.venv\Scripts\python.exe" "%cd%\spark\streaming_job.py"
