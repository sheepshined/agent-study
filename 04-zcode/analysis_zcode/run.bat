@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============================================================
rem  Learn ZCode (s01~s10) launcher
rem  Usage:  run.bat            run all lessons (offline)
rem          run.bat s05        run one lesson
rem ============================================================

if not "%~1"=="" (
    echo ==== %~1 ====
    node "%~1\code.mjs"
    goto :eof
)

set /a passed=0
for /d %%D in (s*) do (
    if exist "%%D\code.mjs" (
        echo.
        echo ============================================================
        echo  %%D
        echo ============================================================
        node "%%D\code.mjs"
        if errorlevel 1 (
            echo [FAILED] %%D
            exit /b 1
        )
        set /a passed+=1
    )
)
echo.
echo All !passed! lessons passed.
