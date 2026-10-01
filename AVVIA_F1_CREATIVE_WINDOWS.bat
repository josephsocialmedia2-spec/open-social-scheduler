@echo off
setlocal
title F1 - PUBBLICAZIONE MANUALE
cd /d "%~dp0"
echo.
echo F1 MANUAL PUBLISH ONLY
echo Il vecchio bootstrap creativo e stato ritirato.
echo Nessun browser AI o generatore grafico verra avviato.
echo.
call publisher\f1_graphics_automation\APRI_RACCOLTA_GRAFICHE.bat
exit /b %ERRORLEVEL%
