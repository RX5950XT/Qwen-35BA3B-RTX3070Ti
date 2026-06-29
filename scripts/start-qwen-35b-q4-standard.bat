@echo off
title Qwen3.6-35B-A3B - Peak Performance Server
echo =============================================================
echo   Qwen3.6-35B-A3B x RTX 3070 Ti - Peak Performance Config
echo   Q4_K_M + MTP + Flash Attention - GPU Expert Offload
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf"
SET "LLAMA_SERVER=bin\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: qwen-q4...
    python scratch\download-model.py qwen-q4
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

echo [INFO] Launching llama-server with HIGH process priority...

start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe 35 --spec-type draft-mtp --spec-draft-n-max 3 --spec-draft-p-min 0.05  -c 32768 -fa on --cache-type-k f16 --cache-type-v f16 --no-mmap --mlock -b 4096 -ub 512 -t 6 -tb 8 --cpu-strict 0 --poll 50 --prio 3 --temp 0.6 --top-p 0.95 --top-k 20 --jinja --host 127.0.0.1 --port 8888 --timeout 300

if %errorlevel% equ 0 (
    echo [SUCCESS] Server launched in high priority window.
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
