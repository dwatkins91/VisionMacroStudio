@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First-time setup: creating the private Python environment...
    py -3.11 -m venv .venv 2>nul
    if errorlevel 1 py -3 -m venv .venv
    if errorlevel 1 (
        echo Python 3.10 or newer was not found. Install Python from python.org and try again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import PySide6, mss, pynput, ultralytics, cv2, PIL, yaml" >nul 2>&1
if errorlevel 1 (
    echo Installing or repairing required packages...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installation failed. Check your internet connection and the messages above.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m app.main
if errorlevel 1 pause
