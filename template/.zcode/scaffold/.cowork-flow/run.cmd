@echo off
rem cowork-flow run launcher (ZCode plugin edition)
rem Delegates to the plugin cache runtime — no local scripts/ required.
setlocal EnableExtensions

set "MIN_PYTHON_LABEL=Python 3.9+"
set "VERSION_CHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)"

set "VERSION_FILE=%~dp0.version"
set "VERSION="
for /f "usebackq delims=" %%A in ("%VERSION_FILE%") do set "VERSION=%%A"

if "%VERSION%"=="" (
  echo Error: cannot determine cowork-flow version (.version missing) >&2
  exit /b 127
)

set "ZCODE_BASE=%ZCODE_HOME%"
if "%ZCODE_BASE%"=="" set "ZCODE_BASE=%USERPROFILE%\.zcode"

set "RUNNER=%ZCODE_BASE%\cli\plugins\cache\zcode-plugins-official\cowork-flow\%VERSION%\hooks\runtime\scripts\run.py"

if not exist "%RUNNER%" (
  echo Error: cowork-flow plugin runtime not found at: >&2
  echo   %RUNNER% >&2
  echo Install the ZCode plugin or run 'cowork-flow init' for standalone. >&2
  exit /b 127
)

rem --- Python interpreter discovery ----------------------------------------
set "SELECTED_PYTHON="
set "SELECTED_PYTHON_ARG="

call :select_python
if errorlevel 1 exit /b %ERRORLEVEL%

if not "%SELECTED_PYTHON_ARG%"=="" (
  "%SELECTED_PYTHON%" "%SELECTED_PYTHON_ARG%" "%RUNNER%" %*
) else (
  "%SELECTED_PYTHON%" "%RUNNER%" %*
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
echo Set %ENV_NAME% to an executable Python 3.9+ interpreter path. 1>&2
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
