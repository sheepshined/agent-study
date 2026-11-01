@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem ============================================================
rem  Learn LangChain (s01~s10) launcher
rem  Usage:  run.bat            run all lessons (offline, zero deps)
rem          run.bat s04        run one lesson
rem ============================================================

if not "%~1"=="" (
    echo ==== %~1 ====
    python "%~1\code.py"
    goto :eof
)

set /a COUNT=0
for /d %%D in (s*) do (
    if exist "%%D\code.py" (
        echo.
        echo ============================================================
        echo  %%D
        echo ============================================================
        python "%%D\code.py"
        if errorlevel 1 (
            echo [FAILED] %%D
            exit /b 1
        )
        set /a COUNT+=1
    )
)
echo.
echo All !COUNT! lessons passed.
