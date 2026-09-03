@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment is missing.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\launch_system.py
if errorlevel 1 pause
endlocal
