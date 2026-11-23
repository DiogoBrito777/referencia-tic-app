@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Abre o app numa porta livre ACIMA de 8510 (comeca em 8511 e procura a proxima livre) e passa a porta ao streamlit com --server.port. Mesmo modelo do ABRIR_V4H.bat.
rem O navegador abre uma vez (o servidor sobe em modo headless pelo .streamlit\config.toml). Para fechar o app, feche esta janela.
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" (echo Python do projeto nao encontrado: rode o INSTALAR.bat ou use ..\.venv. & pause & exit /b 1)
if not exist "saida" mkdir saida
set "PORTA="
for /f %%P in ('powershell -NoProfile -Command "$u=(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue).LocalPort; (8511..8599 | Where-Object { $_ -notin $u } | Select-Object -First 1)"') do set PORTA=%%P
if "%PORTA%"=="" set PORTA=8511
echo Abrindo o app na porta %PORTA% ...
start "" cmd /c "timeout /t 5 >nul & start http://127.0.0.1:%PORTA%"
"%PY%" -m streamlit run "%~dp0app.py" --server.port %PORTA%
pause
