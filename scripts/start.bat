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
endlocal
