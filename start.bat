@echo off
title Maquina de Cortes - Iniciar
set "PROJECT=%~dp0"
if "%PROJECT:~-1%"=="\" set "PROJECT=%PROJECT:~0,-1%"

echo.
echo ============================================
echo   Maquina de Cortes - iniciando aplicacao
echo ============================================
echo.

REM ----- Backend (porta 8000) -----
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [OK] Backend ja esta rodando na porta 8000.
) else (
  echo [..] Iniciando backend em http://127.0.0.1:8000
  start "Maquina de Cortes - Backend" /d "%PROJECT%\backend" cmd /k venv\Scripts\python.exe run.py
)

REM ----- Frontend (porta 5173) -----
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [OK] Frontend ja esta rodando na porta 5173.
) else (
  echo [..] Iniciando frontend em http://localhost:5173
  start "Maquina de Cortes - Frontend" /d "%PROJECT%\frontend" cmd /k npm run dev
)

echo.
echo Abrindo o navegador em alguns segundos...
ping -n 7 127.0.0.1 >nul
start "" http://localhost:5173

echo.
echo Pronto! Feche as janelas de Backend/Frontend para parar a aplicacao.
ping -n 4 127.0.0.1 >nul
exit
