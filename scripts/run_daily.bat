@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set GIT_TERMINAL_PROMPT=0
set NOTIFY_SCRIPT=scripts\send_notification.ps1

cd /d "%~dp0.."

if not exist logs mkdir logs

echo [%date% %time%] START >> logs\daily.log

py scripts\generate_article.py >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: generate >> logs\daily.log
    call :notify failure "ERROR: generate"
    exit /b 1
)

py scripts\fetch_books.py >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: fetch_books >> logs\daily.log
    call :notify failure "ERROR: fetch_books"
    exit /b 1
)

py scripts\build_site.py >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: build_site >> logs\daily.log
    call :notify failure "ERROR: build_site"
    exit /b 1
)

git add -A
if errorlevel 1 (
    echo [%date% %time%] ERROR: git add >> logs\daily.log
    call :notify failure "ERROR: git add"
    exit /b 1
)

git diff --cached --quiet
if not errorlevel 1 (
    echo [%date% %time%] NO CHANGES >> logs\daily.log
    echo [%date% %time%] DONE >> logs\daily.log
    call :notify success "NO CHANGES"
    exit /b 0
)

git commit -m "auto: article %date%" >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: git commit >> logs\daily.log
    call :notify failure "ERROR: git commit"
    exit /b 1
)

git push origin main >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: git push >> logs\daily.log
    call :notify failure "ERROR: git push"
    exit /b 1
)

echo [%date% %time%] DONE >> logs\daily.log
call :notify success "DONE"
exit /b 0

:notify
if exist "%NOTIFY_SCRIPT%" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%NOTIFY_SCRIPT%" -Status "%~1" -Message "%~2" -LogPath "logs\daily.log" >> logs\daily.log 2>&1
)
exit /b 0
