@echo off
title CurseForge Modpack Downloader v4.0
color 0A
cd /d "%~dp0"

cls
echo.
echo   ##################################################
echo   #                                                #
echo   #     CurseForge Modpack Downloader v4.0         #
echo   #                                                #
echo   ##################################################
echo.
echo   Checking environment...
echo.

:: ============================================================
:: Find Python
:: ============================================================

set "PY="

python --version >nul 2>nul && set "PY=python" && goto :found_py
py --version >nul 2>nul && set "PY=py" && goto :found_py

color 0C
echo   [FAIL] Python is not installed!
echo.
echo   Download: https://www.python.org/downloads/
echo   Check: [x] Add Python to PATH
echo.
pause
exit /b

:found_py
echo   [OK] Python found

:: ============================================================
:: Check script file
:: ============================================================

if not exist "curseforge_downloader.py" (
    color 0C
    echo   [FAIL] curseforge_downloader.py not found!
    echo.
    pause
    exit /b
)
echo   [OK] Script file found

:: ============================================================
:: Install libraries if needed
:: ============================================================

%PY% -c "import requests" >nul 2>nul
if errorlevel 1 (
    echo   [..] Installing libraries...
    %PY% -m pip install requests beautifulsoup4 >nul 2>nul
)
echo   [OK] Libraries ready

:: ============================================================
:: Check API key (file must exist AND not be empty)
:: ============================================================

set "KEY_OK=0"
if exist "api_key.txt" (
    for /f "usebackq" %%A in ("api_key.txt") do set "KEY_OK=1"
)
if "%KEY_OK%"=="1" (
    echo   [OK] API key found
    goto :ready
)

echo.
echo   ##################################################
echo   #                                                #
echo   #            API KEY SETUP                       #
echo   #                                                #
echo   ##################################################
echo.
echo   You need a FREE CurseForge API key.
echo.
echo   1. Go to https://console.curseforge.com/
echo   2. Sign in
echo   3. Create API Key
echo   4. Copy and paste it below
echo.

:ask_key
set /p "USER_KEY=   Paste your API key: "
if "%USER_KEY%"=="" goto :ask_key
echo %USER_KEY%> api_key.txt
echo.
echo   [OK] Key saved to api_key.txt

:: ============================================================
:: Ready
:: ============================================================

:ready
echo.
echo   ##################################################
echo   #            Everything is ready!                #
echo   ##################################################
echo.
echo   Press any key to start...
pause >nul

:: ============================================================
:: Run
:: ============================================================

cls
%PY% curseforge_downloader.py

:: ============================================================
:: Done
:: ============================================================

cls
echo.
echo   ##################################################
echo   #                                                #
echo   #          Thank you for using                   #
echo   #     CurseForge Modpack Downloader!             #
echo   #                                                #
echo   ##################################################
echo.
pause
exit /b