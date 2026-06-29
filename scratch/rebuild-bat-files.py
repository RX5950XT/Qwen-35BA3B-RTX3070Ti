import os
import json

# 鎖定工作目錄為專案根目錄，防止執行路徑偏移
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
os.chdir(project_root)

# Fallback default optimal parameters for RTX 3070 Ti (8GB VRAM) + 64GB RAM Dual Channel
best_q4 = {
    "ncmoe": 35,
    "threads": 6,
    "threads_batch": 8,
    "poll": 50,
    "cpu_strict": 0,
    "numa": "none",
    "spec_draft_n_max": 3,
    "spec_draft_p_min": 0.05,
    "cache_type": "f16",
    "ub": 512
}

best_q3 = {
    "ncmoe": 35,
    "threads": 8,
    "threads_batch": 8,
    "poll": 150,
    "cpu_strict": 1,
    "numa": "none",
    "spec_draft_n_max": 2,
    "spec_draft_p_min": 0.12,
    "cache_type": "q8_0",
    "ub": 512
}

# Try loading custom hardware-optimized parameters from auto-tune
results_file = r"scratch\auto-tune-results.json"
hardware_info = "RTX 3070 Ti (8GB) + 64GB RAM Dual-Channel"

if os.path.exists(results_file):
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "qwen-q4" in data:
                best_q4.update(data["qwen-q4"]["best_params"])
            if "qwen-q3" in data:
                best_q3.update(data["qwen-q3"]["best_params"])
            
            # Extract detected hardware if available
            if "hardware" in data:
                cpu = data["hardware"].get("cpu_cores", "8C")
                vram = data["hardware"].get("gpu_vram_mb", 8192)
                hardware_info = f"CPU: {cpu} Cores | GPU VRAM: {vram}MB (Adaptive Tuned)"
        print(f"[INFO] Loaded optimized parameters from auto-tune-results.json: {hardware_info}")
    except Exception as e:
        print(f"[WARNING] Failed to parse auto-tune-results.json: {e}. Fallback to default optimal parameters.")

# Dynamic NUMA argument formulation to prevent invalid value error with llama.cpp
numa_q4 = f"--numa {best_q4['numa']}" if best_q4.get("numa") and best_q4["numa"] != "none" else ""
numa_q3 = f"--numa {best_q3['numa']}" if best_q3.get("numa") and best_q3["numa"] != "none" else ""

# Formulate bat templates dynamically
bat_contents = {
    "start.bat": f"""@echo off
:: Ensure we run from the script directory
cd /d "%~dp0"
:: Set code page to UTF-8 to display characters correctly, fallback gracefully
chcp 65001 >nul 2>&1
title Qwen3.6-35B / Ornith-1.0-35B deployment Console
color 0B

:: Perform environment setup and engine auto-download if missing
call python scratch\\setup-environment.py
if %errorlevel% neq 0 (
    echo [WARNING] Environment setup script exited with error.
    pause
)

:menu
cls
echo =========================================================================
echo   ██████╗  ██╗    ██╗ ███████╗ ███╗   ██╗ ██████╗  ██████╗  ███████╗  ██████╗ 
echo  ██╔═══██╗ ██║    ██║ ██╔════╝ ████╗  ██║ ██╔══██╗ ██╔══██╗ ██╔════╝ ██╔════╝ 
echo  ██║   ██║ ██║ █╗ ██║ █████╗   ██╔██╗ ██║ ██████╔╝ ██████╔╝ █████╗   ██║      
echo  ██║▄▄ ██║ ██║███╗██║ ██╔══╝   ██║╚██╗██║ ██╔═══╝  ██╔══██╗ ██╔══╝   ██║      
echo  ╚██████╔╝ ╚███╔███╔╝ ███████╗ ██║ ╚████║ ██║      ██║  ██║ ███████╗ ╚██████╗ 
echo   ╚══▀▀═╝   ╚══╝╚══╝  ╚══════╝ ╚═╝  ╚═══╝ ╚═╝      ╚═╝  ╚═╝ ╚══════╝  ╚═════╝ 
echo =========================================================================
echo   [ Hardware: {hardware_info} ]
echo =========================================================================
echo.
echo   [Qwen3.6-35B-A3B MoE (with Native MTP)]
echo     1. Launch Qwen3.6-35B - Q4_K_M + MTP (21.7GB)
echo     2. Launch Qwen3.6-35B - Q4_K_M + MTP (Max Context - 8-bit KV, 48K)
echo     3. Launch Qwen3.6-35B - Q3_K_M + MTP (14.0GB)
echo.
echo   [Ornith-1.0-35B MoE (Agentic Reasoner, No MTP)]
echo     4. Launch Ornith-1.0-35B - Q4_K_M (21.7GB)
echo     5. Launch Ornith-1.0-35B - IQ3_M (14.0GB)
echo.
echo   [System Maintenance Tools]
echo     6. Force Stop Llama servers and release VRAM (Stop Server)
echo     7. Run physical RAM bandwidth test (Bandwidth Benchmark)
echo     8. Exit Console
echo.
echo =========================================================================
set "choice="
set /p choice="Please enter choice (1-8): "
if defined choice set "choice=%choice:"=%"

if "%choice%"=="1" goto qwen_q4
if "%choice%"=="2" goto qwen_q4_max_vram
if "%choice%"=="3" goto qwen_iq3
if "%choice%"=="4" goto ornith_q4
if "%choice%"=="5" goto ornith_iq3
if "%choice%"=="6" goto stop_server
if "%choice%"=="7" goto bandwidth_test
if "%choice%"=="8" goto exit_console
goto menu

:qwen_q4
echo.
echo [Launching] Qwen3.6-35B-A3B Q4_K_M + MTP Server...
call scripts\\start-qwen-35b-q4-standard.bat
goto menu

:qwen_q4_max_vram
echo.
echo [Launching] Qwen3.6-35B-A3B Q4_K_M + MTP (Max Context) Server...
call scripts\\start-qwen-35b-q4-48k-context.bat
goto menu

:qwen_iq3
echo.
echo [Launching] Qwen3.6-35B-A3B Q3_K_M + MTP Server...
call scripts\\start-qwen-35b-q3-speed.bat
goto menu

:ornith_q4
echo.
echo [Launching] Ornith-1.0-35B Q4_K_M Server...
call scripts\\start-ornith-35b-q4-standard.bat
goto menu

:ornith_iq3
echo.
echo [Launching] Ornith-1.0-35B IQ3_M Server...
call scripts\\start-ornith-35b-q3-speed.bat
goto menu

:stop_server
echo.
echo [Cleaning] Stopping all servers and releasing memory/VRAM...
call scripts\\stop-all-servers.bat
echo [Done] Cleanup finished.
pause
goto menu

:bandwidth_test
echo.
echo [Testing] Measuring RAM bandwidth via multi-process NumPy...
python scratch\\benchmark-ram-bandwidth-mp.py
echo.
echo [Info] Optimization report available at docs\\local-inference-optimization-and-tuning-report.md.
pause
goto menu

:exit_console
echo.
echo Thank you for using. Happy inference!
timeout /t 2 >nul
exit""",

    "scripts/free-background-vram.bat": """@echo off
title Cleanup Background VRAM Applications
echo =============================================================
echo   清理吃顯存的大型背景程式 ( wallpaper, discord, steam 等 )
echo =============================================================

echo [清理中] 正在檢查與終止常見背景應用程式...
taskkill /f /im wallpaper32.exe >nul 2>&1
taskkill /f /im wallpaper64.exe >nul 2>&1
taskkill /f /im Discord.exe >nul 2>&1
taskkill /f /im Steam.exe >nul 2>&1
taskkill /f /im steamwebhelper.exe >nul 2>&1
taskkill /f /im BambuStudio.exe >nul 2>&1

echo [完成] 背景 VRAM 清理程序結束。""",

    "scripts/stop-all-servers.bat": """@echo off
title Force Kill Llama Servers
echo =============================================================
echo   正在強制終止所有 llama-server.exe 進程以釋放記憶體與顯存
=============================================================

echo [INFO] 正在搜尋並終止 llama-server.exe...
taskkill /f /im llama-server.exe >nul 2>&1

if %errorlevel% equ 0 (
    echo [SUCCESS] 所有 llama-server.exe 進程已成功終止。
) else (
    echo [INFO] 沒有發現運作中的 llama-server.exe 進程。
)""",

    "scripts/start-qwen-35b-q4-standard.bat": f"""@echo off
title Qwen3.6-35B-A3B - Peak Performance Server
echo =============================================================
echo   Qwen3.6-35B-A3B x RTX 3070 Ti - Peak Performance Config
echo   Q4_K_M + MTP + Flash Attention - GPU Expert Offload
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\\Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf"
SET "LLAMA_SERVER=bin\\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: qwen-q4...
    python scratch\\download-model.py qwen-q4
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

echo [INFO] Launching llama-server with HIGH process priority...

start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe {best_q4["ncmoe"]} --spec-type draft-mtp --spec-draft-n-max {best_q4["spec_draft_n_max"]} --spec-draft-p-min {best_q4["spec_draft_p_min"]} {numa_q4} -c 32768 -fa on --cache-type-k {best_q4["cache_type"]} --cache-type-v {best_q4["cache_type"]} --no-mmap --mlock -b 4096 -ub {best_q4["ub"]} -t {best_q4["threads"]} -tb {best_q4["threads_batch"]} --cpu-strict {best_q4["cpu_strict"]} --poll {best_q4["poll"]} --prio 3 --temp 0.6 --top-p 0.95 --top-k 20 --jinja --host 127.0.0.1 --port 8888 --timeout 300

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
pause""",

    "scripts/start-qwen-35b-q4-48k-context.bat": f"""@echo off
title Qwen3.6-35B-A3B - Max Context Performance Server
echo =============================================================
echo   Qwen3.6-35B-A3B x RTX 3070 Ti - Max Context Config
echo   Q4_K_M + MTP + Flash Attention - 8-bit KV Cache + 48K Context
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================
echo.
echo   [!] This mode keeps KV Cache at 8-bit (q8_0) to save VRAM.
echo   [!] Increases Context to 48K (49152) to fully utilize 8GB VRAM.
echo   [!] Automatically cleans up background high-VRAM programs before launch.
echo.

:: Calling VRAM cleanup script...
call "%~dp0free-background-vram.bat"

echo.
echo   [1/2] Checking and terminating existing server processes...
taskkill /f /im llama-server.exe >nul 2>&1

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\\Qwen3.6-35B-A3B-MTP-Q4_K_M.gguf"
SET "LLAMA_SERVER=bin\\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: qwen-q4...
    python scratch\\download-model.py qwen-q4
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

echo [2/2] Launching llama-server with 48K Context (8-bit KV Cache)...
echo.

start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe {best_q4["ncmoe"]} --spec-type draft-mtp --spec-draft-n-max {best_q4["spec_draft_n_max"]} --spec-draft-p-min {best_q4["spec_draft_p_min"]} {numa_q4} -c 49152 -fa on --cache-type-k q8_0 --cache-type-v q8_0 --no-mmap --mlock -b 4096 -ub {best_q4["ub"]} -t {best_q4["threads"]} -tb {best_q4["threads_batch"]} --cpu-strict {best_q4["cpu_strict"]} --poll {best_q4["poll"]} --prio 3 --temp 0.6 --top-p 0.95 --top-k 20 --jinja --host 127.0.0.1 --port 8888 --timeout 300

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
pause""",

    "scripts/start-qwen-35b-q3-speed.bat": f"""@echo off
title Qwen3.6-35B - Start 3-bit Server (Peak Performance)
echo =============================================================
echo   Qwen3.6-35B-A3B x RTX 3070 Ti - Peak Performance 3-bit Config
echo   Q3_K_M + MTP + Flash Attention - GPU Expert Offload
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\\Qwen3.6-35B-A3B-MTP-Q3_K_M.gguf"
SET "LLAMA_SERVER=bin\\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: qwen-q3...
    python scratch\\download-model.py qwen-q3
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

:: Launch llama-server with HIGH process priority and optimized parameters
start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe {best_q3["ncmoe"]} --spec-type draft-mtp --spec-draft-n-max {best_q3["spec_draft_n_max"]} --spec-draft-p-min {best_q3["spec_draft_p_min"]} {numa_q3} -c 32768 -fa on --cache-type-k {best_q3["cache_type"]} --cache-type-v {best_q3["cache_type"]} --no-mmap --mlock -b 4096 -ub {best_q3["ub"]} -t {best_q3["threads"]} -tb {best_q3["threads_batch"]} --cpu-strict {best_q3["cpu_strict"]} --poll {best_q3["poll"]} --prio 3 --temp 0.6 --top-p 0.95 --jinja --host 127.0.0.1 --port 8888 --timeout 300

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
echo [SUCCESS] You can close the server by running stop-server.bat
echo =============================================================
pause""",

    "scripts/start-ornith-35b-q4-standard.bat": f"""@echo off
title Ornith-1.0-35B - Q4_K_M Peak Performance Server
echo =============================================================
echo   Ornith-1.0-35B x RTX 3070 Ti - Peak Performance Config
echo   Q4_K_M (No MTP) + Flash Attention - GPU Expert Offload
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\\Ornith-1.0-35B-Q4_K_M.gguf"
SET "LLAMA_SERVER=bin\\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: ornith-q4...
    python scratch\\download-model.py ornith-q4
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

echo [INFO] Launching llama-server with HIGH process priority...

start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe {best_q4["ncmoe"]} {numa_q4} -c 32768 -fa on --cache-type-k {best_q4["cache_type"]} --cache-type-v {best_q4["cache_type"]} --no-mmap --mlock -b 4096 -ub {best_q4["ub"]} -t {best_q4["threads"]} -tb {best_q4["threads_batch"]} --cpu-strict {best_q4["cpu_strict"]} --poll {best_q4["poll"]} --prio 3 --temp 0.6 --top-p 0.95 --jinja --host 127.0.0.1 --port 8888 --timeout 300

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
pause""",

    "scripts/start-ornith-35b-q3-speed.bat": f"""@echo off
title Ornith-1.0-35B - IQ3_M Peak Performance Server
echo =============================================================
echo   Ornith-1.0-35B x RTX 3070 Ti - Peak Performance 3-bit Config
echo   IQ3_M + Flash Attention - GPU Expert Offload
echo   OS Priority: HIGH - CPU Pinning: STRICT - Polling: OFF
echo =============================================================

:: Ensure we are running from the project root
cd /d "%~dp0.."

SET "MODEL_PATH=models\\Ornith-1.0-35B-IQ3_M.gguf"
SET "LLAMA_SERVER=bin\\llama-server.exe"

:: Check if model exists, download on demand
if not exist "%MODEL_PATH%" (
    echo [INFO] %MODEL_PATH% was not found!
    echo [INFO] Initiating automatic download for model: ornith-q3...
    python scratch\\download-model.py ornith-q3
    if not exist "%MODEL_PATH%" (
        echo [ERROR] Model download failed. Cannot start server.
        pause
        exit /b 1
    )
)

echo [INFO] Launching llama-server with HIGH process priority...

start /high "" "%LLAMA_SERVER%" -m "%MODEL_PATH%" -np 1 -ngl 99 -ncmoe {best_q3["ncmoe"]} {numa_q3} -c 32768 -fa on --cache-type-k {best_q3["cache_type"]} --cache-type-v {best_q3["cache_type"]} --no-mmap --mlock -b 4096 -ub {best_q3["ub"]} -t {best_q3["threads"]} -tb {best_q3["threads_batch"]} --cpu-strict {best_q3["cpu_strict"]} --poll {best_q3["poll"]} --prio 3 --temp 0.6 --top-p 0.95 --jinja --host 127.0.0.1 --port 8888 --timeout 300

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
pause"""
}

# Ensure scripts/ directory exists
os.makedirs("scripts", exist_ok=True)

for filepath, content in bat_contents.items():
    # Force Windows CRLF line endings
    with open(filepath, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content.strip() + "\r\n")
    print(f"Rebuilt: {filepath} ({len(content)} chars)")

print("All batch files rebuilt successfully.")
