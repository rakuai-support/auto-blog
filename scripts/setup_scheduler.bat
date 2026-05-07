@echo off
REM ========================================
REM タスクスケジューラに日次タスクを登録
REM 管理者権限で実行すること
REM ========================================

schtasks /create ^
  /tn "AutoBlog_DailyArticle" ^
  /tr "C:\Users\utaka\rakuai\projects\1000チャレンジ\auto-blog\scripts\run_daily.bat" ^
  /sc daily ^
  /st 06:00 ^
  /rl HIGHEST ^
  /f

echo タスク登録完了: 毎日06:00に自動実行されます
pause
