@echo off
rem Dars Studio oynasini ochadi (API + pywebview, yoki brauzer).
cd /d "%~dp0"
rem Maxine (Eye Contact): paketda runtime\maxine; ishlab chiqish muhitida yonidagi "eye contact" loyihasidan
if not defined DARS_MAXINE_DIR if not exist "runtime\maxine" if exist "..\eye contact\runtime\maxine" set "DARS_MAXINE_DIR=%~dp0..\eye contact\runtime\maxine"
if exist "runtime\python\pythonw.exe" (
  start "" "runtime\python\pythonw.exe" -m darsstudio.app_window
) else (
  ".venv\Scripts\python.exe" -m darsstudio.app_window
)
