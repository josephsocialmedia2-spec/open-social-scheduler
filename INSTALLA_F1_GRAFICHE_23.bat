@echo off
setlocal
cd /d "%~dp0"
call publisher\f1_graphics_automation\INSTALLA_AUTOMAZIONE_23.bat
if errorlevel 1 (
  echo.
  echo INSTALLAZIONE F1 NON COMPLETATA.
  exit /b 1
)
exit /b 0
