@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Referência TIC: instalação (cria .venv nesta pasta) ===
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version || (echo Python 3 não encontrado. Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH". & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || (echo Falha ao criar o .venv. & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-cache-dir -r requirements.txt || (echo Falha ao instalar as bibliotecas. & pause & exit /b 1)
if not exist "saida" mkdir saida
echo.
echo Instalação concluída. Agora dê dois cliques em ABRIR_APP.bat.
pause
