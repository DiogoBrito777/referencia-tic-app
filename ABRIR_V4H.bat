@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem v4h: abre numa porta livre ACIMA de 8510 (comeca em 8511 e procura a proxima livre). Para fechar o app, feche esta janela.
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" (echo Python do projeto nao encontrado: rode o INSTALAR.bat ou use ..\.venv. & pause & exit /b 1)
if not exist "saida" mkdir saida
set "PORTA="
for /f %%P in ('powershell -NoProfile -Command "$u=(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue).LocalPort; (8511..8599 | Where-Object { $_ -notin $u } | Select-Object -First 1)"') do set PORTA=%%P
if "%PORTA%"=="" set PORTA=8511
echo Abrindo a v4h na porta %PORTA% ...
start "" cmd /c "timeout /t 5 >nul & start http://localhost:%PORTA%"
"%PY%" -m streamlit run "%~dp0app.py" --server.port %PORTA%
pause
