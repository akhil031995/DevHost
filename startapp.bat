@echo off
:: Launch DevHost with no background console window.
:: Uses pythonw.exe (windowless Python) so no cmd terminal stays open.
:: UAC elevation is handled inside the Python script via ctypes.

set "SCRIPT_DIR=%~dp0DevHost"

:: Derive pythonw.exe from the python.exe on PATH (same directory)
for /f "delims=" %%i in ('where python') do (
    set "PYTHONW=%%~dpi\pythonw.exe"
    goto :launch
)

:launch
if not exist "%PYTHONW%" (
    :: Last resort — use start /b to detach from this console
    start /b "" python "%SCRIPT_DIR%\main.py"
    exit /b 0
)

:: start "" prevents pythonw from inheriting this console window
start "" "%PYTHONW%" "%SCRIPT_DIR%\main.py"
