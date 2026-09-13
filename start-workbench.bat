@echo off
rem ===========================================================================
rem  HTML Fiddle - start the local visual HTML editor (Windows entry point)
rem
rem  Double-click to pick a file, or drag an .html file onto this .bat,
rem  or call it from a terminal:  start-workbench.bat "D:\path\page.html"
rem
rem  Messages are kept ASCII here on purpose: cmd renders a UTF-8 .bat using
rem  the OEM code page, which would garble Chinese. All Chinese output comes
rem  from launcher.py, which writes through the Windows console Unicode API.
rem
rem  Python discovery lives in scripts\find-python.bat. It validates candidates
rem  by actually running them, because the zero-byte Microsoft Store
rem  "python.exe" stub is found by `where` yet always exits 9009.
rem ===========================================================================
setlocal
set "HERE=%~dp0"
set "PY="

call "%HERE%scripts\find-python.bat" "%HERE%"

if not defined PY (
  echo.
  echo [ERROR] No usable Python 3.9+ found on this machine.
  echo.
  echo         A likely culprit was skipped on purpose: the zero-byte
  echo         "python.exe" App Execution Alias stub shipped under
  echo             ...\AppData\Local\Microsoft\WindowsApps\
  echo         `where` finds it, but it is not a real interpreter and it
  echo         always exits with 9009. Installing a real Python fixes this.
  echo.
  echo         Install Python 3.9 or newer from:
  echo             https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during setup,
  echo         or install Miniconda / Anaconda instead.
  echo.
  pause
  exit /b 2
)

echo Using Python: %PY%
rem `call` keeps us safe if the discovered interpreter is a .bat/.cmd shim
rem (pyenv-win ships those): without it, control would chain away and the
rem exit-code handling below would never run.
call %PY% "%HERE%scripts\launcher.py" %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
  echo.
  echo [exit code: %CODE%]
  pause
) else (
  rem Keep the window open on a bare double-click so the address stays readable.
  if "%~1"=="" pause
)

endlocal & exit /b %CODE%
