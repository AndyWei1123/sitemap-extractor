@echo off
rem Double-click to start Sitemap Extractor on this computer.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo First run: setting up, this takes a minute...
    python -m venv .venv
    if errorlevel 1 (
        echo Python 3.10 or newer is required: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo Installing packages failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
)

echo Sitemap Extractor is running at http://127.0.0.1:8000/
echo Close this window to stop it.
".venv\Scripts\python.exe" -m web
pause
