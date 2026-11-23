@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Rode primeiro o INSTALAR.bat. & pause & exit /b 1)
if not exist "saida" mkdir saida
".venv\Scripts\python.exe" -I -u "%~dp0ferramenta.py"
pause
