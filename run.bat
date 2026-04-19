@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

echo ============================================
echo HTR Race Charts Converter - Run
echo ============================================

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Run setup.bat first, then run this script again.
    popd >nul
    exit /b 1
)

echo Activating virtual environment...
call ".venv\Scripts\activate.bat" || goto :error

echo Launching app...
python src/main.py || goto :error

popd >nul
exit /b 0

:error
echo.
echo Application exited with an error. See details above.
popd >nul
exit /b 1
