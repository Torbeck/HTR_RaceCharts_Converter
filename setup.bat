@echo off
setlocal EnableExtensions
set "FAILED_STEP="

echo =============================================
echo HTR Race Charts Converter - Windows Setup
echo =============================================

echo.
echo [1/4] Checking Python installation...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo Install Python 3.10+ and enable "Add Python to PATH", then run setup.bat again.
    exit /b 1
)

echo.
if exist ".venv\Scripts\activate.bat" (
    echo [2/4] Virtual environment already exists: .venv
) else (
    echo [2/4] Creating virtual environment: .venv
    set "FAILED_STEP=creating virtual environment (.venv)"
    python -m venv .venv
    if errorlevel 1 goto :error
)

echo.
echo [3/4] Activating virtual environment...
set "FAILED_STEP=activating virtual environment"
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :error

echo.
echo [4/4] Upgrading pip and installing dependencies...
set "FAILED_STEP=upgrading pip"
python -m pip install --upgrade pip
if errorlevel 1 goto :error

set "FAILED_STEP=installing dependencies from requirements.txt"
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Setup complete. You can now run the app with run.bat
exit /b 0

:error
echo.
if defined FAILED_STEP (
    echo ERROR: Setup failed while %FAILED_STEP%.
    echo Please review the error details above.
) else (
    echo ERROR: Setup failed. Please review the error details above.
)
exit /b 1
