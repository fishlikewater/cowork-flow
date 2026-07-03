@echo off
setlocal EnableExtensions

set "MIN_PYTHON_LABEL=Python 3.8+"
set "VERSION_CHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
set "WORKFLOW_DIR=%~dp0"

set "RUNTIME_SCRIPTS=%WORKFLOW_DIR%scripts"

if not exist "%RUNTIME_SCRIPTS%\run.py" (
  echo Error: cowork-flow runtime not found. >&2
  exit /b 127
)

where python3 >nul 2>nul
if not errorlevel 1 (
  set "PYTHONPATH=%RUNTIME_SCRIPTS%;%PYTHONPATH%"
  python3 "%RUNTIME_SCRIPTS%\run.py" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if not errorlevel 1 (
  set "PYTHONPATH=%RUNTIME_SCRIPTS%;%PYTHONPATH%"
  python "%RUNTIME_SCRIPTS%\run.py" %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHONPATH=%RUNTIME_SCRIPTS%;%PYTHONPATH%"
  py -3 "%RUNTIME_SCRIPTS%\run.py" %*
  exit /b %ERRORLEVEL%
)

echo Error: %MIN_PYTHON_LABEL% required but not found. >&2
exit /b 127
