@echo off
taskkill /f /im ngrok.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 >nul

start /B "" "C:\kakaobot\ngrok.exe" http 5000
timeout /t 5 >nul

powershell -NoProfile -ExecutionPolicy Bypass -File "C:\kakaobot\update_kakao_url.ps1"

start /B "" python "C:\kakaobot\kakao_server.py"
echo done
pause
