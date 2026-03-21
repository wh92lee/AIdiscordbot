@echo off
taskkill /f /im ngrok.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 >nul

start /B "" "C:\kakaobot\ngrok.exe" http 5000
timeout /t 5 >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command "$url = (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels[0].public_url; Write-Host 'ngrok:' $url; $body = '{\"url\":\"' + $url + '\",\"token\":\"bsbot-kakao-token\"}'; try { Invoke-RestMethod -Uri 'http://168.107.17.244:8765' -Method POST -Body $body -ContentType 'application/json'; Write-Host 'update ok' } catch { Write-Host 'update fail:' $_.Exception.Message }"

start /B "" python "C:\kakaobot\kakao_server.py"

echo done
pause
