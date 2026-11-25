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

rem auto-detect machine profile → Spark sizing (manual env still wins)
if not defined SPARK_MASTER if not defined SPARK_DRIVER_MEMORY if not defined NLP_TORCH_THREADS (
  for /f %%c in ('%NUMBER_OF_PROCESSORS%') do set CORES=%%c
  for /f "tokens=2 delims==" %%m in ('wmic ComputerSystem get TotalPhysicalMemory /value 2^>nul ^| find "="') do set RAM_BYTES=%%m
  set /a RAM_GB=%RAM_BYTES%/1073741824 2>nul || set RAM_GB=8
  if %RAM_GB% GEQ 24 if %CORES% GEQ 8 (
    set "SPARK_MASTER=local[6]" & set "SPARK_DRIVER_MEMORY=4g" & set "NLP_TORCH_THREADS=8"
  ) else if %RAM_GB% GEQ 8 (
    set "SPARK_MASTER=local[4]" & set "SPARK_DRIVER_MEMORY=2g" & set "NLP_TORCH_THREADS=4"
  ) else (
    set "SPARK_MASTER=local[2]" & set "SPARK_DRIVER_MEMORY=1g" & set "NLP_TORCH_THREADS=2"
  )
)
if not defined SPARK_MASTER set "SPARK_MASTER=local[4]"
if not defined SPARK_DRIVER_MEMORY set "SPARK_DRIVER_MEMORY=2g"
if not defined NLP_TORCH_THREADS set "NLP_TORCH_THREADS=4"
echo [profile] cores=%CORES% ram=%RAM_GB%GB master=%SPARK_MASTER% driver=%SPARK_DRIVER_MEMORY% threads=%NLP_TORCH_THREADS%

"%cd%\.venv\Scripts\python.exe" "%cd%\spark\streaming_job.py"
