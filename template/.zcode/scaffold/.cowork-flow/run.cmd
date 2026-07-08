@echo off
rem cowork-flow run launcher (ZCode plugin edition)
rem Delegates to the plugin cache runtime — no local scripts/ required.
setlocal EnableExtensions

set "VERSION_FILE=%~dp0.version"
set "VERSION="
for /f "usebackq delims=" %%A in ("%VERSION_FILE%") do set "VERSION=%%A"

if "%VERSION%"=="" (
  echo Error: cannot determine cowork-flow version (.version missing) >&2
  exit /b 127
)

set "ZCODE_BASE=%ZCODE_HOME%"
if "%ZCODE_BASE%"=="" set "ZCODE_BASE=%USERPROFILE%\.zcode"

set "PLUGIN_RUN=%ZCODE_BASE%\cli\plugins\cache\zcode-plugins-official\cowork-flow\%VERSION%\hooks\runtime\run.cmd"

if not exist "%PLUGIN_RUN%" (
  echo Error: cowork-flow plugin runtime not found at: >&2
  echo   %PLUGIN_RUN% >&2
  echo Install the ZCode plugin or run 'cowork-flow init' for standalone. >&2
  exit /b 127
)

"%PLUGIN_RUN%" %*
exit /b %ERRORLEVEL%
