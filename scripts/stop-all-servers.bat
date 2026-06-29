@echo off
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
)
