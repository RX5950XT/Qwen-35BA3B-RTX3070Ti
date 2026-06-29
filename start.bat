@echo off
:: Ensure we run from the script directory
cd /d "%~dp0"
:: Set code page to UTF-8 to display characters correctly, fallback gracefully
chcp 65001 >nul 2>&1
title Qwen3.6-35B / Ornith-1.0-35B deployment Console
color 0B

:: Perform environment setup and engine auto-download if missing
call python scratch\setup-environment.py
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
echo   [ Hardware: RTX 3070 Ti (8GB) + 64GB RAM Dual-Channel ]
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
call scripts\start-qwen-35b-q4-standard.bat
goto menu

:qwen_q4_max_vram
echo.
echo [Launching] Qwen3.6-35B-A3B Q4_K_M + MTP (Max Context) Server...
call scripts\start-qwen-35b-q4-48k-context.bat
goto menu

:qwen_iq3
echo.
echo [Launching] Qwen3.6-35B-A3B Q3_K_M + MTP Server...
call scripts\start-qwen-35b-q3-speed.bat
goto menu

:ornith_q4
echo.
echo [Launching] Ornith-1.0-35B Q4_K_M Server...
call scripts\start-ornith-35b-q4-standard.bat
goto menu

:ornith_iq3
echo.
echo [Launching] Ornith-1.0-35B IQ3_M Server...
call scripts\start-ornith-35b-q3-speed.bat
goto menu

:stop_server
echo.
echo [Cleaning] Stopping all servers and releasing memory/VRAM...
call scripts\stop-all-servers.bat
echo [Done] Cleanup finished.
pause
goto menu

:bandwidth_test
echo.
echo [Testing] Measuring RAM bandwidth via multi-process NumPy...
python scratch\benchmark-ram-bandwidth-mp.py
echo.
echo [Info] Optimization report available at docs\local-inference-optimization-and-tuning-report.md.
pause
goto menu

:exit_console
echo.
echo Thank you for using. Happy inference!
timeout /t 2 >nul
exit
