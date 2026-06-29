@echo off
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

echo [完成] 背景 VRAM 清理程序結束。
