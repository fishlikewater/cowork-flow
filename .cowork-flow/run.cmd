@echo off
setlocal EnableExtensions

set "MIN_PYTHON_LABEL=Python 3.8+"
set "VERSION_CHECK=import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)"
set "WORKFLOW_DIR=%~dp0"
set "SCRIPTS_DIR=%WORKFLOW_DIR%scripts"
set "SELECTED_PYTHON="
set "SELECTED_PYTHON_ARG="
set "REST_ARGS="

if "%~1"=="" goto usage_error

set "COMMAND_NAME=%~1"
if not "%~2"=="" (
  for /F "tokens=1,* delims= " %%A in ("%*") do set "REST_ARGS=%%B"
)

if /I "%COMMAND_NAME%"=="-h" goto usage
if /I "%COMMAND_NAME%"=="--help" goto usage
if /I "%COMMAND_NAME%"=="help" goto usage
if /I "%COMMAND_NAME%"=="python" goto run_python_passthrough
if /I "%COMMAND_NAME%"=="resume" goto run_resume
if /I "%COMMAND_NAME%"=="task" goto run_task
if /I "%COMMAND_NAME%"=="change" goto run_change
if /I "%COMMAND_NAME%"=="get-context" goto run_get_context
if /I "%COMMAND_NAME%"=="get_context" goto run_get_context
if /I "%COMMAND_NAME%"=="get-developer" goto run_get_developer
if /I "%COMMAND_NAME%"=="get_developer" goto run_get_developer
if /I "%COMMAND_NAME%"=="init-developer" goto run_init_developer
if /I "%COMMAND_NAME%"=="init_developer" goto run_init_developer
if /I "%COMMAND_NAME%"=="add-session" goto run_add_session
if /I "%COMMAND_NAME%"=="add_session" goto run_add_session

if exist "%SCRIPTS_DIR%\%COMMAND_NAME%.py" (
  call :run_script "%SCRIPTS_DIR%\%COMMAND_NAME%.py"
  exit /b %ERRORLEVEL%
)

echo 错误：未知 cowork-flow 命令：%COMMAND_NAME% 1>&2
call :print_usage 1>&2
exit /b 2

:usage
call :print_usage
exit /b 0

:usage_error
call :print_usage 1>&2
exit /b 2

:run_python_passthrough
call :exec_python %REST_ARGS%
exit /b %ERRORLEVEL%

:run_resume
call :run_script "%SCRIPTS_DIR%\resume.py"
exit /b %ERRORLEVEL%

:run_task
call :run_script "%SCRIPTS_DIR%\task.py"
exit /b %ERRORLEVEL%

:run_change
call :run_script "%SCRIPTS_DIR%\change.py"
exit /b %ERRORLEVEL%

:run_get_context
call :run_script "%SCRIPTS_DIR%\get_context.py"
exit /b %ERRORLEVEL%

:run_get_developer
call :run_script "%SCRIPTS_DIR%\get_developer.py"
exit /b %ERRORLEVEL%

:run_init_developer
call :run_script "%SCRIPTS_DIR%\init_developer.py"
exit /b %ERRORLEVEL%

:run_add_session
call :run_script "%SCRIPTS_DIR%\add_session.py"
exit /b %ERRORLEVEL%

:print_usage
echo 用法：
echo   .\.cowork-flow\run.cmd ^<command^> [args...]
echo   .\.cowork-flow\run.cmd python [python-args...]
echo.
echo 常用 command：
echo   resume
echo   task
echo   change
echo   get-context
echo   get-developer
echo   init-developer
echo   add-session
echo.
echo 解释器选择顺序：
echo   COWORK_FLOW_PYTHON -^> PYTHON -^> python3 -^> python -^> py -3
exit /b 0

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

echo 错误：%ENV_NAME% 指向的解释器不可用或版本低于 %MIN_PYTHON_LABEL%：%ENV_VALUE% 1>&2
echo 请设置 %ENV_NAME% 为可执行的 Python 3.8+ 解释器路径。 1>&2
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

echo 错误：需要 %MIN_PYTHON_LABEL%，但未找到可用解释器。 1>&2
echo 已尝试：COWORK_FLOW_PYTHON、PYTHON、python3、python、py -3。 1>&2
echo 可设置 COWORK_FLOW_PYTHON=C:\Path\To\python.exe 后重试。 1>&2
exit /b 127

:exec_python
call :select_python
if errorlevel 1 exit /b %ERRORLEVEL%

if not "%SELECTED_PYTHON_ARG%"=="" (
  "%SELECTED_PYTHON%" "%SELECTED_PYTHON_ARG%" %*
) else (
  "%SELECTED_PYTHON%" %*
)
exit /b %ERRORLEVEL%

:run_script
set "SCRIPT_PATH=%~1"

if not exist "%SCRIPT_PATH%" (
  echo 错误：找不到脚本：%SCRIPT_PATH% 1>&2
  exit /b 2
)

call :exec_python "%SCRIPT_PATH%" %REST_ARGS%
exit /b %ERRORLEVEL%
