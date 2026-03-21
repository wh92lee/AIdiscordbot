# 셋팅 가이드 (리눅스 서버 + Windows 로컬 PC)

## 구성
- **리눅스 서버**: 디스코드 봇 실행
- **Windows PC**: 카카오톡 메시지 전송 (kakao_server.py + ngrok)

---

## 1. 리눅스 서버 셋팅

### 1-1. 소스 다운로드
```bash
git clone https://github.com/wh92lee/AIdiscordbot.git
cd AIdiscordbot
```

### 1-2. 가상환경 및 패키지 설치
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gspread google-auth
```

### 1-3. 환경 파일 생성

**.env**
```
DISCORD_TOKEN=디스코드_봇_토큰
```

**settings.json**
```json
{
  "discord": {
    "alert_channel_id": 알림채널ID,
    "voice_channel_id": 음성채널ID,
    "command_prefix": "!"
  },
  "sheet": {
    "spreadsheet_name": "구글시트이름",
    "sheet_name": "참여율체크"
  },
  "kakao": {
    "server_url": "",
    "token": "bsbot-kakao-token"
  }
}
```

### 1-4. 구글 서비스 계정 키 파일 배치
`bsbot-428416-2282f2d345ef.json` 파일을 AIdiscordbot 폴더에 배치

### 1-5. 방화벽 포트 오픈 (Oracle 클라우드 기준)
```bash
sudo iptables -I INPUT -p tcp --dport 8765 -j ACCEPT
```
Oracle 콘솔 Security List에도 8765 포트 수신 규칙 추가

### 1-6. 봇 실행
```bash
source venv/bin/activate
python bot.py
```

---

## 2. Windows PC 셋팅

### 2-1. 패키지 설치
```powershell
pip install flask pyautogui pyperclip
```

### 2-2. 폴더 및 파일 준비
`C:\kakaobot\` 폴더 생성 후 아래 파일 배치:
- `kakao_server.py` (GitHub에서 다운로드)
- `ngrok.exe` (https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip)
- `update_kakao_url.ps1` (GitHub에서 다운로드)
- `start_kakao.bat` (GitHub에서 다운로드)

### 2-3. start_kakao.vbs 생성
메모장으로 `C:\kakaobot\start_kakao.vbs` 파일 생성:
```vbs
CreateObject("WScript.Shell").Run "C:\kakaobot\start_kakao.bat", 0, False
```

### 2-4. ngrok 계정 연동
ngrok.com 가입 후 authtoken 발급:
```powershell
cd C:\kakaobot
.\ngrok.exe authtoken 발급받은_토큰
```

### 2-5. kakao_server.py 채팅방 이름 확인
`kakao_server.py` 25번째 줄:
```python
ROOM_NAME = "카카오톡_채팅방_이름"
```
실제 채팅방 이름과 정확히 일치하는지 확인

### 2-6. 실행
`start_kakao.vbs` 더블클릭

---

## 3. 매번 PC 재부팅 시
1. 카카오톡 실행
2. `start_kakao.vbs` 더블클릭 (ngrok + kakao_server.py 자동 시작 + 봇 서버 URL 자동 업데이트)

---

## 4. 봇 업데이트 시
```bash
cd AIdiscordbot
git pull
source venv/bin/activate
python bot.py
```
> settings.json, .env, 구글 키 파일은 git에서 제외되므로 유지됨
