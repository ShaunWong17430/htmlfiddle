@echo off
rem ===========================================================================
rem  Shared Python discovery for HTML Fiddle's Windows entry points.
rem
rem  Called as:  call "%~dp0find-python.bat" "<project-root>"
rem  Result   :  sets PY (e.g. "py -3" or "C:\...\python.exe"), errorlevel 0/1
rem
rem  Why this file exists instead of a plain `where python` check:
rem
rem  Windows ships ZERO-BYTE "App Execution Alias" stubs, typically at
rem      %LOCALAPPDATA%\Microsoft\WindowsApps\python.exe
rem  `where` FINDS them, so a presence-only test concludes "Python is installed".
rem  Running one with no Store Python installed prints "Python was not found..."
rem  and exits with 9009 -- which is exactly the bare [exit code: 9009] a user
rem  sees when that directory precedes the real interpreter in PATH.
rem
rem  So this script never trusts mere presence. It skips WindowsApps outright and
rem  validates every candidate by ACTUALLY RUNNING it against our own launcher
rem  (`launcher.py --version`, which exits non-zero below Python 3.9).
rem
rem  Two layers on purpose: the WindowsApps rule is the fast path for the known
rem  trap, and the run-it-and-see check catches any other unusable interpreter
rem  (broken install, wrong architecture, a stub from some other vendor).
rem
rem  No setlocal on purpose: PY must survive into the caller.
rem ===========================================================================

set "PY="
set "HWF_ROOT=%~1"
if "%HWF_ROOT%"=="" set "HWF_ROOT=%~dp0."
rem A doubled separator (root already ends with "\") is harmless on Windows, so
rem there is no need to strip it -- and stripping would turn "C:\" into "C:".

rem --- 1) the py launcher, when present: it manages registered interpreters ---
where py >nul 2>nul
if not errorlevel 1 call :try_py

rem --- 2) every python / python3 on PATH, skipping the Store stubs ---
if not defined PY call :scan python
if not defined PY call :scan python3

rem --- 3) common install locations (PATH may simply not have them) ---
if not defined PY call :common

if defined PY exit /b 0
exit /b 1


:try_py
call py -3 "%HWF_ROOT%\scripts\launcher.py" --version >nul 2>nul
if errorlevel 1 exit /b 0
set "PY=py -3"
exit /b 0


:scan
rem %1 = executable name. `where` may return several hits; try each in order.
for /f "delims=" %%P in ('where %1 2^>nul') do call :try_path "%%~fP"
exit /b 0


:common
for %%D in (
  "%USERPROFILE%\miniconda3"
  "%USERPROFILE%\anaconda3"
  "%USERPROFILE%\Anaconda3"
  "%LOCALAPPDATA%\miniconda3"
  "%LOCALAPPDATA%\Continuum\anaconda3"
  "%LOCALAPPDATA%\Programs\Python\Python313"
  "%LOCALAPPDATA%\Programs\Python\Python312"
  "%LOCALAPPDATA%\Programs\Python\Python311"
  "%LOCALAPPDATA%\Programs\Python\Python310"
  "%LOCALAPPDATA%\Programs\Python\Python39"
  "%ProgramFiles%\Python313"
  "%ProgramFiles%\Python312"
  "%ProgramFiles%\Python311"
  "%ProgramFiles%\Python310"
  "%ProgramFiles%\Python39"
) do call :try_path "%%~D\python.exe"
exit /b 0


:try_path
rem %1 = candidate interpreter path. Keep the first one that really works.
if defined PY exit /b 0
set "CAND=%~1"
if not exist "%CAND%" exit /b 0
rem Layer 1: skip the zero-byte Microsoft Store alias, which always exits 9009.
echo "%CAND%" | find /i "WindowsApps" >nul && exit /b 0
rem Layer 2: prove it works. `call` matters here -- a candidate may be a
rem .bat/.cmd wrapper (conda and pyenv ship shims like that), and invoking
rem another batch file without `call` chains into it, so control never returns
rem and the caller fails silently.
call "%CAND%" "%HWF_ROOT%\scripts\launcher.py" --version >nul 2>nul
if errorlevel 1 exit /b 0
rem Store the quoted path so a directory containing spaces still works.
set "PY="%CAND%""
exit /b 0
