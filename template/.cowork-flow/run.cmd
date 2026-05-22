@echo off
setlocal EnableExtensions

set "MIN_PYTHON_LABEL=Python 3.8+"
set "VERSION_CHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
set "WORKFLOW_DIR=%~dp0"
set "RUNNER_SCRIPT=%WORKFLOW_DIR%scripts\run.py"
set "SELECTED_PYTHON="
set "SELECTED_PYTHON_ARG="

call :select_python
if errorlevel 1 exit /b %ERRORLEVEL%

if not "%SELECTED_PYTHON_ARG%"=="" (
  "%SELECTED_PYTHON%" "%SELECTED_PYTHON_ARG%" "%RUNNER_SCRIPT%" %*
) else (
  "%SELECTED_PYTHON%" "%RUNNER_SCRIPT%" %*
)
exit /b %ERRORLEVEL%

:candidate_is_valid
set "CANDIDATE_CMD=%~1"
set "CANDIDATE_ARG=%~2"

where "%CANDIDATE_CMD%" >nul 2>nul
if errorlevel 1 (
  if not exist "%CANDIDATE_CMD%" exit /b 1
)

if not "%CANDIDATE_ARG%"=="" (
  "%CANDIDATE_CMD%" "%CANDIDATE_ARG%" -c "%VERSION_CHECK%" >nul 2>nul
) else (
  "%CANDIDATE_CMD%" -c "%VERSION_CHECK%" >nul 2>nul
)
exit /b %ERRORLEVEL%

:select_explicit_python
set "ENV_NAME=%~1"
set "ENV_VALUE=%~2"

call :candidate_is_valid "%ENV_VALUE%" ""
if not errorlevel 1 (
  set "SELECTED_PYTHON=%ENV_VALUE%"
  set "SELECTED_PYTHON_ARG="
  exit /b 0
)

echo Error: %ENV_NAME% does not point to a usable %MIN_PYTHON_LABEL% interpreter: %ENV_VALUE% 1>&2
echo Set %ENV_NAME% to an executable Python 3.8+ interpreter path. 1>&2
exit /b 127

:select_python
set "SELECTED_PYTHON="
set "SELECTED_PYTHON_ARG="

if not "%COWORK_FLOW_PYTHON%"=="" (
  call :select_explicit_python "COWORK_FLOW_PYTHON" "%COWORK_FLOW_PYTHON%"
  exit /b %ERRORLEVEL%
)

if not "%PYTHON%"=="" (
  call :select_explicit_python "PYTHON" "%PYTHON%"
  exit /b %ERRORLEVEL%
)

call :candidate_is_valid "python3" ""
if not errorlevel 1 (
  set "SELECTED_PYTHON=python3"
  exit /b 0
)

call :candidate_is_valid "python" ""
if not errorlevel 1 (
  set "SELECTED_PYTHON=python"
  exit /b 0
)

call :candidate_is_valid "py" "-3"
if not errorlevel 1 (
  set "SELECTED_PYTHON=py"
  set "SELECTED_PYTHON_ARG=-3"
  exit /b 0
)

echo Error: %MIN_PYTHON_LABEL% is required, but no usable interpreter was found. 1>&2
echo Tried: COWORK_FLOW_PYTHON, PYTHON, python3, python, py -3. 1>&2
echo Set COWORK_FLOW_PYTHON=C:\Path\To\python.exe and retry. 1>&2
exit /b 127
