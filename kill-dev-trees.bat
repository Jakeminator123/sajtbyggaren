@echo off
REM Wrapper för kill-dev-trees.py så Windows-dubbelklick funkar
REM oavsett om Python är globalt på PATH eller bara i .venv.
REM
REM Kör Python från (i prioordning):
REM   1. .venv\Scripts\python.exe (om venv finns)
REM   2. python på PATH (global Python-installation)
REM   3. Annars rapporterar fel.

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe kill-dev-trees.py
    goto :end
)

where python >nul 2>nul
if %errorlevel% == 0 (
    python kill-dev-trees.py
    goto :end
)

echo.
echo  ! Python hittades inte.
echo    Installera Python (https://www.python.org/) eller skapa .venv:
echo      python -m venv .venv
echo      .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.

:end
echo.
pause
