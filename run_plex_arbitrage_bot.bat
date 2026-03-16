@echo off
setlocal

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%~dp0plex_arbitrage_bot.py" %*
  exit /b %ERRORLEVEL%
)

python "%~dp0plex_arbitrage_bot.py" %*
exit /b %ERRORLEVEL%
