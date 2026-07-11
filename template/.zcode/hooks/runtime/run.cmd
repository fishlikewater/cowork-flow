@echo off
REM cowork-flow run launcher (ZCode plugin edition, Windows)
REM Runs commands using the plugin's bundled Python runtime.
setlocal EnableDelayedExpansion

set "WORKFLOW_DIR=%~dp0"
set "RUNTIME_SCRIPTS=%WORKFLOW_DIR%scripts"
set "RUNNER_SCRIPT=%RUNTIME_SCRIPTS%\run.py"

if not exist "%RUNNER_SCRIPT%" (
  echo Error: run.py not found in runtime: %RUNTIME_SCRIPTS% >&2
  exit /b 127
)

set "SELECTED_PYTHON="
for %%p in (python3 python py) do (
  where /q %%p 2>nul
  if !errorlevel! equ 0 (
    %%p -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if !errorlevel! equ 0 (
      set "SELECTED_PYTHON=%%p"
      goto :found_python
    )
  )
)
echo Error: Python 3.9+ required but not found. >&2
exit /b 127

:found_python
set "PYTHONPATH=%RUNTIME_SCRIPTS%;%PYTHONPATH%"
%SELECTED_PYTHON% "%RUNNER_SCRIPT%" %*
