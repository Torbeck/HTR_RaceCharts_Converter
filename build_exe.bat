@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

echo =============================================
echo HTR Race Charts Converter - Build Windows EXE
echo =============================================

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pyinstaller is not available on PATH.
    echo Install it first, then run this script again.
    popd >nul
    exit /b 1
)

pyinstaller --clean --noconfirm HTR_RaceCharts_Converter.spec
if errorlevel 1 (
    echo.
    echo ERROR: EXE build failed.
    popd >nul
    exit /b 1
)

echo.
echo Build complete.
echo Output: dist\HTR_RaceCharts_Converter\HTR_RaceCharts_Converter.exe
popd >nul
exit /b 0
