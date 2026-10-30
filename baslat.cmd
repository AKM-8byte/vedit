@echo off
rem VEdit arayüzünü açar. Bir .vedit.json dosyasını bu dosyanın üstüne sürükleyip bırakabilirsin.
cd /d "%~dp0"
".venv\Scripts\vedit.exe" gui %*
