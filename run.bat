@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [error] Virtual environment not found.
    echo Create it first:
    echo   py -3.12 -m venv .venv
    echo   .venv\Scripts\python -m pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "src\main.py" %*
