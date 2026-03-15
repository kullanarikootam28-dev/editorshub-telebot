@echo off
title EditorsHub AURA Bot
color 0A

:: This script automatically restarts the bot if it crashes on Windows.
:: Render automatically restarts crashed processes, so this is only needed locally.

:loop
echo [%time%] Starting EditorsHub AURA Bot...
echo.

:: Run the python process using the virtual environment
"F:\TELEGRAML BOT\.venv\Scripts\python.exe" bot.py

:: If python.exe exits, it reaches this point
echo.
echo [%time%] ⚠️ Bot crashed or was stopped!
echo Restarting in 10 seconds...
timeout /t 10 /nobreak > nul
echo.
echo ----------------------------------------
goto loop
