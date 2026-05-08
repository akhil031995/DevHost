@echo off
:: DevHost — PyInstaller build script
:: Run from the DevHost\ directory: build.bat

setlocal

echo ============================================
echo  DevHost Build Script
echo ============================================
echo.

:: Verify Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Add Python to PATH.
    pause
    exit /b 1
)

:: Install / upgrade dependencies
echo [1/4] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause
    exit /b 1
)

echo [2/4] Cleaning previous build artifacts...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist app.spec del /q app.spec

echo [3/4] Running PyInstaller...
pyinstaller ^
    --onefile ^
    --windowed ^
    --uac-admin ^
    --name DevHost ^
    --add-data "config;config" ^
    --add-data "templates;templates" ^
    --add-data "assets;assets" ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    app.py

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [4/4] Build complete!
echo.
echo  EXE location: dist\DevHost.exe
echo.
echo  NOTE: Run DevHost.exe as Administrator (UAC manifest is embedded).
echo.

pause
endlocal
