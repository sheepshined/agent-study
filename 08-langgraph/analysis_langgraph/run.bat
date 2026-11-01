@echo off
rem One-click runner for all lessons (only s* dirs that contain code.py; shared/ skipped).
rem Keep this file ASCII-only: cmd.exe mis-parses batch files with multi-byte chars
rem once chcp 65001 is active. Force UTF-8 for Python output instead.
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

if not "%~1"=="" (
    echo ==== %~1 ====
    python "%~1\code.py"
    goto :eof
)

set /a pass=0
set /a fail=0
for /d %%D in (s*) do (
  if exist "%%D\code.py" (
    echo ==================== %%D / python code.py ====================
    python "%%D\code.py" > nul 2>&1
    if !errorlevel! equ 0 (
      echo [PASS] %%D
      set /a pass+=1
    ) else (
      echo [FAIL] %%D
      python "%%D\code.py"
      set /a fail+=1
    )
  )
)

if !fail! equ 0 (
  echo.
  echo All !pass! lessons passed.
  exit /b 0
) else (
  echo.
  echo !fail! lesson^(s^) FAILED, !pass! passed.
  exit /b 1
)
