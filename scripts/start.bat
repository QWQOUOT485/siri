@echo off
setlocal
cd /d "%~dp0.."
title Windows Siri Agent
if not exist ".venv\Scripts\python.exe" (
  echo Setup is incomplete. Run scripts\setup.ps1 in PowerShell first.
  pause
  exit /b 1
)
echo Windows Siri Agent starting on http://0.0.0.0:8000
echo Press Ctrl+C to stop the agent.
".venv\Scripts\python.exe" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Agent failed to start or stopped with exit code %EXIT_CODE%.
  echo Check whether another Agent instance is already using port 8000.
  pause
)
endlocal
exit /b %EXIT_CODE%
