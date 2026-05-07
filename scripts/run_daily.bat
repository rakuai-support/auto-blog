@echo off
chcp 65001 >nul

cd /d "%~dp0.."

if not exist logs mkdir logs

echo [%date% %time%] START >> logs\daily.log

py scripts\generate_article.py >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] ERROR: generate >> logs\daily.log
    exit /b 1
)

py scripts\fetch_books.py >> logs\daily.log 2>&1

py scripts\build_site.py >> logs\daily.log 2>&1

git add -A
git commit -m "auto: article %date%"
git push origin main

echo [%date% %time%] DONE >> logs\daily.log
