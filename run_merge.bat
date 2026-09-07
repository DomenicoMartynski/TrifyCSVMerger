@echo off
setlocal

cd /d "%~dp0"
python "merge_txt_to_csv_format.py"

if errorlevel 1 (
  echo.
  echo Merge failed. Check messages above.
) else (
  echo.
  echo Merge completed successfully.
)

echo.
pause
