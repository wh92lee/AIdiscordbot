# 셋팅 가이드 (Windows 로컬 PC 단독 운영)

## 구성
- **Windows PC**: 디스코드 봇 + 카카오톡 메시지 전송 모두 실행
- ngrok, 외부 서버 불필요

---

## 1. 패키지 설치
```powershell
pip install discord.py[voice] python-dotenv edge-tts gspread google-auth flask pyautogui pyperclip
```

---

## 2. 소스 다운로드
```powershell
git clone https://github.com/wh92lee/AIdiscordbot.git
cd AIdiscordbot
```

---

## 3. 환경 파일 생성

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
    "server_url": "http://localhost:5000",
    "token": "bsbot-kakao-token"
  }
}
```
> 리눅스 서버 버전과 유일한 차이점: `server_url`을 `http://localhost:5000`으로 고정

---

## 4. 구글 서비스 계정 키 파일 배치
`bsbot-428416-2282f2d345ef.json` 파일을 AIdiscordbot 폴더에 배치

---

## 5. kakao_server.py 채팅방 이름 확인
`kakao_server.py` 25번째 줄:
```python
ROOM_NAME = "카카오톡_채팅방_이름"
```
실제 채팅방 이름과 정확히 일치하는지 확인

---

## 6. 실행 순서
터미널 1 - 카카오 서버:
```powershell
cd C:\AIdiscordbot
python kakao_server.py
```

터미널 2 - 디스코드 봇:
```powershell
cd C:\AIdiscordbot
python bot.py
```

---

## 7. 매번 PC 재부팅 시
1. 카카오톡 실행
2. `kakao_server.py` 실행
3. `bot.py` 실행

> 자동화 원하면 시작프로그램에 두 파일 모두 등록

---

## 8. 소스 코드 변경 사항
리눅스 서버 버전 대비 **settings.json만 변경**하면 됩니다:
- `server_url`: `""` → `"http://localhost:5000"`
- ngrok, update_kakao_url.ps1, start_kakao.bat, start_kakao.vbs 불필요

---

## 9. 봇 업데이트 시
```powershell
cd AIdiscordbot
git pull
```
> settings.json, .env, 구글 키 파일은 git에서 제외되므로 유지됨
