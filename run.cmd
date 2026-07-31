@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment was not found.
  echo Run setup.cmd first.
  exit /b 1
)

if "%CADCHECK_PORT%"=="" set "CADCHECK_PORT=8000"
set "PYTHONIOENCODING=utf-8"

echo Starting server on http://127.0.0.1:%CADCHECK_PORT%
".venv\Scripts\python.exe" main.py
