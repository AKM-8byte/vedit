@echo off
rem Sanal ortamı kurar (başka bir bilgisayarda ilk kez çalıştırırken).
cd /d "%~dp0"
if not exist ".venv" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[mcp,dev]"
".venv\Scripts\python.exe" tools\ornekleri_uret.py
echo.
echo Kurulum tamam. Arayuzu acmak icin: baslat.cmd
pause
