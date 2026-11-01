@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ============================================================
rem  Learn OpenCode (s01~s10) launcher
rem  Usage:  run.bat          run all lessons (offline)
rem          run.bat s04      run one lesson
rem  Only s* directories that contain code.mjs are executed
rem  (shared/ and other tool directories are skipped).
rem ============================================================

if not "%~1"=="" (
    echo ==== %~1 ====
    node "%~1\code.mjs"
    goto :eof
)

set /a COUNT=0
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
        set /a COUNT+=1
    )
)
echo.
echo All !COUNT! lessons passed.
