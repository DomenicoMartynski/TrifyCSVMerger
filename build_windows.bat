@echo off
REM ===================================================================
REM  Build the Windows app: "Trify CSV Merger.exe"
REM  Double-click this file. The finished .exe lands in the dist\ folder.
REM  Requirements: Python 3.10+ from python.org (includes Tkinter).
REM ===================================================================
setlocal
cd /d "%~dp0"

echo ==^> Trify CSV Merger - Windows build
echo.

REM Find a Python with Tkinter.
set "PYTHON_BIN="
for %%P in (py python) do (
  if not defined PYTHON_BIN (
    %%P -c "import tkinter" >nul 2>&1 && set "PYTHON_BIN=%%P"
  )
)

if not defined PYTHON_BIN (
  echo ERROR: No Python with Tkinter was found.
  echo Install Python from https://www.python.org/downloads/ ^(check "Add to PATH"^),
  echo then run this script again.
  echo.
  pause
  exit /b 1
)
echo Using Python: %PYTHON_BIN%

REM Fresh virtual environment for a clean build.
if exist .venv_build rmdir /s /q .venv_build
%PYTHON_BIN% -m venv .venv_build
call .venv_build\Scripts\activate.bat

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt pyinstaller pillow

REM Regenerate the icon (safe to re-run).
python build\make_icon.py

echo.
echo ==^> Packaging with PyInstaller...
if exist "dist\Trify CSV Merger.exe" del /q "dist\Trify CSV Merger.exe"
pyinstaller build\CSVMerger.spec --noconfirm --distpath dist --workpath build\_work

echo.
echo ===================================================================
echo  Done!  Your app is here:
echo    dist\Trify CSV Merger.exe
echo.
echo  Double-click it to run. To share it, just send that single .exe.
echo  (Windows SmartScreen may warn on first run: More info -^> Run anyway.)
echo ===================================================================
echo.
pause
