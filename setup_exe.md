# 셋팅 가이드 (Windows exe 단독 운영)

## 구성
- **Windows PC**: bot.exe + kakao_server.exe 실행
- Python 설치 불필요 (배포용)

---

## 1. 빌드 환경 준비 (개발자용 - 빌드할 때만 필요)

### 1-1. pyinstaller 설치
```powershell
pip install pyinstaller
```

### 1-2. bot.exe 빌드
```powershell
cd AIdiscordbot
pyinstaller --onefile --name bot bot.py
```

### 1-3. kakao_server.exe 빌드
```powershell
pyinstaller --onefile --name kakao_server kakao_server.py
```

빌드 완료 후 `dist\` 폴더에 `bot.exe`, `kakao_server.exe` 생성됨

---

## 2. 배포 폴더 구성
아래 파일들을 한 폴더에 모아서 보관:

```
C:\botfolder\
    bot.exe                          ← 빌드 결과물
    kakao_server.exe                 ← 빌드 결과물
    .env                             ← 직접 작성
    settings.json                    ← 직접 작성
    bsbot-428416-2282f2d345ef.json   ← 구글 서비스 계정 키
    bosses.txt                       ← GitHub에서 다운로드
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

---

## 4. kakao_server.exe 채팅방 이름 확인
빌드 전 `kakao_server.py` 25번째 줄 확인:
```python
ROOM_NAME = "카카오톡_채팅방_이름"
```
실제 채팅방 이름과 정확히 일치하는지 확인 후 빌드

---

## 5. 실행
1. 카카오톡 실행
2. `kakao_server.exe` 더블클릭
3. `bot.exe` 더블클릭

---

## 6. 업데이트 시
소스 변경이 있을 때만 재빌드 필요:
```powershell
pyinstaller --onefile --name bot bot.py
pyinstaller --onefile --name kakao_server kakao_server.py
```
빌드 후 `dist\` 폴더의 exe 파일만 교체
> settings.json, .env, 구글 키 파일은 그대로 유지

---

## 7. 주의사항
- `settings.json`, `.env`, 구글 키 파일은 exe와 **같은 폴더**에 있어야 함
- 카카오톡이 실행 중이어야 메시지 전송 가능
- PC 재부팅 시 `kakao_server.exe` → `bot.exe` 순서로 실행
