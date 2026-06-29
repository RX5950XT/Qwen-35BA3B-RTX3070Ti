@echo off
title Ornith-1.0-35B - IQ3_M Peak Performance Server
echo =============================================================
echo   Ornith-1.0-35B x RTX 3070 Ti - Peak Performance 3-bit Config
echo   IQ3_M + Flash Attention - GPU Expert Offload
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\Ornith-1.0-35B-IQ3_M.gguf"
SET "LLAMA_SERVER=bin\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: ornith-q3...
    python scratch\download-model.py ornith-q3
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

echo [INFO] Launching llama-server with HIGH process priority...

start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe 35  -c 32768 -fa on --cache-type-k q8_0 --cache-type-v q8_0 --no-mmap --mlock -b 4096 -ub 512 -t 8 -tb 8 --cpu-strict 1 --poll 150 --prio 3 --temp 0.6 --top-p 0.95 --jinja --host 127.0.0.1 --port 8888 --timeout 300

if %errorlevel% equ 0 (
    echo [SUCCESS] 3-bit Server launched in high priority window.
    goto wait_ready
) else (
    echo [ERROR] Failed to start llama-server.
    goto end_start
)

:wait_ready
echo [SUCCESS] API is hosting at: http://127.0.0.1:8888/v1
echo [INFO] Waiting for server to load model (checking health endpoint)...
for /L %%i in (1,1,60) do (
    timeout /t 1 >nul 2>&1
    curl -s -f http://127.0.0.1:8888/health >nul 2>&1
    if not errorlevel 1 (
        echo [SUCCESS] Server is ready! Opening Web UI...
        start http://127.0.0.1:8888
        goto end_start
    )
)
echo [WARNING] Server loading took too long. Skipped waiting. Please open http://127.0.0.1:8888 manually.

:end_start
echo =============================================================
pause
