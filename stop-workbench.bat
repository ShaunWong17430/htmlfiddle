@echo off
rem ===========================================================================
rem  HTML Fiddle - stop the background editor service (Windows entry point)
rem
rem  Python discovery is shared with start-workbench.bat; see
rem  scripts\find-python.bat for why a plain `where python` check is not enough.
rem ===========================================================================
setlocal
set "HERE=%~dp0"
set "PY="

call "%HERE%scripts\find-python.bat" "%HERE%"

if not defined PY (
  echo.
  echo [ERROR] No usable Python 3.9+ found on this machine.
  echo         See start-workbench.bat for details and install hints.
  echo.
  pause
  exit /b 2
)

rem `call` keeps us safe if the discovered interpreter is a .bat/.cmd shim
rem (pyenv-win ships those): without it, control would chain away and the
rem exit-code handling below would never run.
call %PY% "%HERE%scripts\launcher.py" --stop %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
  echo.
  echo [exit code: %CODE%]
  pause
) else (
  rem Let a double-clicked window stay up long enough to read the result.
  rem `ping` is used instead of `timeout`, which errors out whenever stdin is
  rem redirected (piped or <nul) instead of attached to a console.
  ping -n 4 127.0.0.1 >nul
)

endlocal & exit /b %CODE%
