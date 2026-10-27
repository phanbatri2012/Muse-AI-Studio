@echo off
chcp 65001 >nul
title MUSE AI STUDIO - Automated Video Generator
cd /d "%~dp0"

echo ============================================================
echo   🚀 MUSE AI STUDIO - Automated Video Generator
echo ============================================================
echo Đang khởi động giao diện Desktop App...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)

if %errorlevel% neq 0 (
    echo.
    echo [LỖI] Ứng dụng đã dừng với mã lỗi %errorlevel%.
    pause
)
