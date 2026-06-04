@echo off
setlocal enabledelayedexpansion
title Mouse Axis Remapper - Windows Setup

echo ============================================================
echo   Mouse Axis Remapper - Windows Setup
echo ============================================================
echo.

:: ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python not found in PATH.
    echo.
    echo  Please install Python 3.9 - 3.12 from https://python.org
    echo  and make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Found Python %PYVER%

:: ── Create virtual environment ───────────────────────────────────────────────
if not exist venv\ (
    echo  Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo  ERROR: Failed to create virtual environment.
        pause & exit /b 1
    )
) else (
    echo  Virtual environment already exists, skipping.
)

:: ── Install PyQt6 ────────────────────────────────────────────────────────────
echo  Installing PyQt6 (pre-built wheel)...
venv\Scripts\pip install --quiet --only-binary :all: PyQt6
if %errorlevel% neq 0 (
    echo  ERROR: Failed to install PyQt6.
    echo  Make sure you have internet access, then try again.
    pause & exit /b 1
)

echo.
echo  ============================================================
echo   Setup complete!
echo  ============================================================
echo.
echo   To run:        double-click  run.bat
echo                  or:  venv\Scripts\python main.py
echo.
echo   To build .exe: venv\Scripts\pip install pyinstaller
echo                  venv\Scripts\pyinstaller --onefile --windowed
echo                    --name mouse-axis-remapper main.py
echo.
pause
