@echo off
chcp 65001 >nul

schtasks /delete /tn "AutoBlog_DailyArticle" /f 2>nul

schtasks /create /tn "AutoBlog_DailyArticle" /xml "%~dp0task_definition.xml" /f

echo.
echo Done
pause
