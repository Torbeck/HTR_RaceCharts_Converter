@echo off
setlocal EnableExtensions

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
    python -m venv .venv || goto :error
)

echo.
echo [3/4] Activating virtual environment...
call ".venv\Scripts\activate.bat" || goto :error

echo.
echo [4/4] Upgrading pip and installing dependencies...
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error

echo.
echo Setup complete. You can now run the app with run.bat
exit /b 0

:error
echo.
echo Setup failed. Please review the error messages above.
exit /b 1
