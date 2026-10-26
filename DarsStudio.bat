@echo off
rem Dars Studio oynasini ochadi (API + pywebview, yoki brauzer).
cd /d "%~dp0"
if exist "runtime\python\pythonw.exe" (
  start "" "runtime\python\pythonw.exe" -m darsstudio.app_window
) else (
  ".venv\Scripts\python.exe" -m darsstudio.app_window
)
