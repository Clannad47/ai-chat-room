@echo off
chcp 65001 >nul
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" echo.
echo 按任意键关闭窗口...
pause >nul
exit /b %CODE%
