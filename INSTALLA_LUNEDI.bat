@echo off
chcp 65001 >nul
title Open Social Scheduler - Installazione Lunedì
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "iwr 'https://raw.githubusercontent.com/josephsocialmedia2-spec/open-social-scheduler/main/windows/INSTALLA_APERTURA_LUNEDI.ps1' -UseBasicParsing | iex"
echo.
pause
