@echo off
REM ========================================
REM 毎日自動実行バッチ
REM タスクスケジューラから呼ばれる
REM ========================================

cd /d "C:\Users\utaka\rakuai\projects\1000チャレンジ\auto-blog"

echo [%date% %time%] 自動記事生成を開始 >> logs\daily.log

REM 1. 記事生成
py scripts\generate_article.py >> logs\daily.log 2>&1
if errorlevel 1 (
    echo [%date% %time%] 記事生成でエラー発生 >> logs\daily.log
    exit /b 1
)

REM 2. サイトビルド
py scripts\build_site.py >> logs\daily.log 2>&1

REM 3. Git push（GitHub Pagesへデプロイ）
git add -A
git commit -m "auto: 記事追加 %date%"
git push origin main

echo [%date% %time%] 完了 >> logs\daily.log
