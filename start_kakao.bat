@echo off
echo [카카오봇] ngrok 시작 중...

:: 기존 ngrok/python 프로세스 종료
taskkill /f /im ngrok.exe >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1
timeout /t 2 >nul

:: ngrok 백그라운드 실행
start /B "" "C:\kakaobot\ngrok.exe" http 5000
echo [카카오봇] ngrok 실행됨, 5초 대기...
timeout /t 5 >nul

:: ngrok 주소 확인 및 봇 서버 업데이트 (로그 파일 저장)
echo [카카오봇] ngrok 주소 확인 중...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$url = (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels[0].public_url; Write-Host '[카카오봇] ngrok 주소:' $url; $body = '{\"url\":\"' + $url + '\",\"token\":\"bsbot-kakao-token\"}'; try { Invoke-RestMethod -Uri 'http://168.107.17.244:8765' -Method POST -Body $body -ContentType 'application/json'; Write-Host '[카카오봇] 봇 서버 주소 업데이트 완료' } catch { Write-Host '[카카오봇] 업데이트 실패:' $_.Exception.Message }" > "C:\kakaobot\start_log.txt" 2>&1
type "C:\kakaobot\start_log.txt"

:: kakao_server.py 백그라운드 실행
echo [카카오봇] kakao_server.py 시작 중...
start /B "" pythonw "C:\kakaobot\kakao_server.py"

echo.
echo [카카오봇] 모든 서비스 시작 완료!
pause
