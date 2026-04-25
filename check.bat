@echo off
setlocal
cd /d "%~dp0"

set "PYTHONPATH=%~dp0src"
".venv\Scripts\python.exe" -m doppelvoice --check
pause
