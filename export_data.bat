@echo off
REM Double-click to download all AstroVinod bot data into an Excel file and open it.
cd /d "%~dp0"
".venv\Scripts\python.exe" export_data.py
if errorlevel 1 (
  echo.
  echo Export failed - check your internet connection and the DATABASE_URL in .env
  pause
  exit /b 1
)
for /f "delims=" %%F in ('dir /b /o-d "exported_data\AstroVinod_data_*.xlsx"') do (
  start "" "exported_data\%%F"
  goto :done
)
:done
