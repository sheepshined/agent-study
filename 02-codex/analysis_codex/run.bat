@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

rem ============================================================
rem  Learn OpenAI Codex (s01~s10) launcher -- offline, zero deps
rem  Usage:  run.bat                  run all lessons (stop on fail)
rem          run.bat s07_apply_patch  run one lesson (directory name)
rem  NOTE: keep this file ASCII-only; cmd.exe mis-parses batch
rem        files containing multi-byte chars once chcp 65001 is on.
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
