@echo off
rem ───────────────────────────────────────────────────────────────
rem  build.bat  —  PyInstaller build + clean   (UAC-friendly, CI-friendly)
rem ───────────────────────────────────────────────────────────────

rem 0. Всегда работаем из папки, где лежит .bat
cd /d "%~dp0"

rem 1. Признак CI (GitHub Actions, GitLab, Azure, …)
if "%CI%"=="true" set IS_CI=1
if "%1"=="--ci"   set IS_CI=1

rem 2. Если не в CI и не admin → перезапускаем скрипт с Run-as-Admin
if not defined IS_CI (
    net session >nul 2>&1
    if %errorlevel% neq 0 (
        powershell -NoProfile -Command ^
          "Start-Process -FilePath '%comspec%' -ArgumentList '/c','\"%~f0\" --elevated' -Verb RunAs -WorkingDirectory '%~dp0'"
        exit /b
    )
)

rem 3. При втором входе (elevated) удаляем служебный флаг
if "%1"=="--elevated" shift

rem ───── переменные путей ────────────────────────────────────────
setlocal EnableDelayedExpansion
set ROOT=%cd%
set OUT=%ROOT%\zapret                 rem итоговая папка рядом с .bat
set WORK=%TEMP%\pyi_%RANDOM%

rem ───── чистим старые кеши ──────────────────────────────────────
for /d /r "%ROOT%" %%d in (__pycache__) do rd /s /q "%%d" 2>nul

rem ───── генерируем version_info.txt ─────────────────────────────
python "%ROOT%\zapretbuild.py" || goto :failed

rem ───── гасим старый zapret.exe (если запущен, локально) ───────
if not defined IS_CI (
    tasklist /fi "imagename eq zapret.exe" | find /i "zapret.exe" >nul
    if not errorlevel 1 (
        taskkill /f /t /im zapret.exe 2>nul
    )
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

rem ───── удаляем временный workpath и кеши ──────────────────────
rd /s /q "%WORK%" 2>nul
for /d /r "%ROOT%" %%d in (__pycache__) do rd /s /q "%%d" 2>nul

rem ───── завершение ─────────────────────────────────────────────
if defined IS_CI exit /b 0
pause
goto :eof

:failed
if defined IS_CI exit /b 1
pause
exit /b 1
