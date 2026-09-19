@echo off
setlocal
cd /d "%~dp0.."
title Windows Siri Agent
set "AGENT_PORT=8000"
if exist ".env" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do if /I "%%A"=="SIRI_AGENT_PORT" set "AGENT_PORT=%%B"
)
if not exist ".venv\Scripts\python.exe" (
  echo Setup is incomplete. Run scripts\setup.ps1 in PowerShell first.
  pause
  exit /b 1
)
echo Windows Siri Agent starting on http://0.0.0.0:%AGENT_PORT%
echo Press Ctrl+C to stop the agent.
".venv\Scripts\python.exe" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Agent failed to start or stopped with exit code %EXIT_CODE%.
  echo Check whether another Agent instance is already using port %AGENT_PORT%.
  pause
)
endlocal
exit /b %EXIT_CODE%
