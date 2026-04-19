@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul

echo =============================================
echo HTR Race Charts Converter - Build Windows EXE
echo =============================================

set "MODE=%~1"
if "%MODE%"=="" set "MODE=onedir"

if /I "%MODE%"=="onefile" (
  set "SPEC=HTR_RaceCharts_Converter.onefile.spec"
  set "EXPECTED=dist\HTR_RaceCharts_Converter.exe"
) else if /I "%MODE%"=="onedir" (
  set "SPEC=HTR_RaceCharts_Converter.spec"
  set "EXPECTED=dist\HTR_RaceCharts_Converter\HTR_RaceCharts_Converter.exe"
) else (
  echo Usage:
  echo   build_exe.bat onedir
  echo   build_exe.bat onefile
  popd >nul
  exit /b 2
)

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pyinstaller is not available on PATH.
    echo Install it first, then run this script again.
    popd >nul
    exit /b 1
)

echo.
echo Mode: %MODE%
echo Spec: %SPEC%
echo.

if not exist "%SPEC%" (
    echo ERROR: Spec file not found: %SPEC%
    popd >nul
    exit /b 1
)

REM Clean previous outputs (optional but avoids confusion)
if exist build rmdir /s /q build >nul 2>&1
if exist dist rmdir /s /q dist >nul 2>&1

pyinstaller --clean --noconfirm "%SPEC%"
if errorlevel 1 (
    echo.
    echo ERROR: EXE build failed.
    popd >nul
    exit /b 1
)

echo.
echo Build complete.
echo Expected output: %EXPECTED%
if exist "%EXPECTED%" (
  echo OK: Found %EXPECTED%
) else (
  echo WARNING: Expected output not found at: %EXPECTED%
  echo Check the dist\ folder contents.
)

popd >nul
exit /b 0