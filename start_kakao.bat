@echo off
echo [카카오봇] ngrok 시작 중...

:: 기존 ngrok 프로세스 종료
taskkill /f /im ngrok.exe >nul 2>&1
timeout /t 2 >nul

:: ngrok 백그라운드 실행
start /B "" "C:\kakaobot\ngrok.exe" http 5000

:: ngrok 준비 대기
timeout /t 5 >nul

:: ngrok API로 새 주소 확인 후 봇 서버에 전송
powershell -Command ^
  "$url = (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels[0].public_url;" ^
  "Write-Host '[카카오봇] ngrok 주소:' $url;" ^
  "$body = @{url=$url; token='bsbot-kakao-token'} | ConvertTo-Json;" ^
  "try { Invoke-RestMethod -Uri 'http://168.107.17.244:8765' -Method POST -Body $body -ContentType 'application/json'; Write-Host '[카카오봇] 봇 서버 주소 업데이트 완료'; } catch { Write-Host '[카카오봇] 봇 서버 업데이트 실패:' $_.Exception.Message }" ^
  " | Out-File -FilePath 'C:\kakaobot\start_log.txt' -Encoding utf8

:: kakao_server.py 백그라운드 실행
echo [카카오봇] kakao_server.py 시작 중...
start /B "" pythonw "C:\kakaobot\kakao_server.py"

echo [카카오봇] 모든 서비스 시작 완료!
echo 로그: C:\kakaobot\start_log.txt
pause
