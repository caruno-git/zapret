@echo off
rem ───────────────────────────────────────────────────────────────
rem  build.bat  —  PyInstaller build + clean   (UAC-friendly)
rem ───────────────────────────────────────────────────────────────

rem 0. Всегда работаем из папки, где лежит .bat
cd /d "%~dp0"

rem 1. Если не admin → перезапускаем скрипт с Run-as-Admin
::  в elevated-копию передаём аргумент  --elevated
::  и каталог через  -WorkingDirectory
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command ^
      "Start-Process -FilePath '%comspec%' -ArgumentList '/c','\"%~f0\" --elevated' -Verb RunAs -WorkingDirectory '%~dp0'"
    exit /b
)

rem 2. (опционально) при повторном входе можно удалить флаг аргумента
if "%1"=="--elevated" shift

rem ───── переменные путей ────────────────────────────────────────
setlocal EnableDelayedExpansion
set ROOT=%cd%
set OUT=%ROOT%\..\zapret
set WORK=%TEMP%\pyi_%RANDOM%

rem ───── чистим старые кеши ──────────────────────────────────────
for /d /r "%ROOT%" %%d in (__pycache__) do rd /s /q "%%d" 2>nul

rem ───── генерируем version_info.txt ─────────────────────────────
python "%ROOT%\zapretbuild.py" || goto :failed

rem ───── гасим старый zapret.exe (если запущен) ─────────────────
tasklist /fi "imagename eq zapret.exe" | find /i "zapret.exe" >nul
if not errorlevel 1 (
    taskkill /f /t /im zapret.exe 2>nul
)

rem ───── PyInstaller ────────────────────────────────────────────
python -m PyInstaller ^
        --onefile ^
        --console ^
        --windowed ^
        --icon "%ROOT%\zapret.ico" ^
        --name zapret ^
        --version-file "%ROOT%\version_info.txt" ^
        --hidden-import=win32com ^
        --hidden-import=win32com.client ^
        --hidden-import=pythoncom ^
        --workpath "%WORK%" ^
        --distpath "%OUT%" ^
        "%ROOT%\main.py" || goto :failed

rem ───── удаляем временный workpath и свежие __pycache__ ─────────
rd /s /q "%WORK%" 2>nul
for /d /r "%ROOT%" %%d in (__pycache__) do rd /s /q "%%d" 2>nul

pause
goto :eof

:failed
pause
exit /b 1