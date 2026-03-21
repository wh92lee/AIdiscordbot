"""
카카오톡 알림 서버 (Windows 로컬 PC 실행용)

[설치]
pip install flask pyautogui pygetwindow pyperclip

[실행]
python kakao_server.py

[ngrok 터널링]
ngrok http 5000
→ 출력된 https://xxxx.ngrok.io 주소를 settings.json의 kakao_server_url에 입력
"""

from flask import Flask, request, jsonify
import pyautogui
import pyperclip
import threading
import time
import ctypes
import ctypes.wintypes

app = Flask(__name__)

ROOM_NAME = "해운대Z-보스타임"
SECRET_TOKEN = "bsbot-kakao-token"   # 리눅스 봇과 동일하게 설정

send_lock = threading.Lock()


def find_hwnd(title_keyword):
    """윈도우 핸들(hwnd) 찾기"""
    import ctypes
    result = []
    def callback(hwnd, _):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_keyword in buf.value:
                result.append((hwnd, buf.value))
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    ctypes.windll.user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result


def activate_hwnd(hwnd):
    """창 활성화"""
    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)


def find_and_open_room():
    """채팅방 창 찾기 (열려있으면 활성화, 없으면 메인창에서 검색)"""
    rooms = find_hwnd(ROOM_NAME)
    if rooms:
        activate_hwnd(rooms[0][0])
        return True

    kakao_wins = find_hwnd("카카오톡")
    if not kakao_wins:
        print("[카카오] 카카오톡 창을 찾을 수 없습니다.")
        return False

    activate_hwnd(kakao_wins[0][0])
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.4)
    pyperclip.copy(ROOM_NAME)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(0.8)
    return True


def send_message(message):
    """카카오톡 채팅방에 메시지 전송"""
    with send_lock:
        try:
            print(f"[카카오] 창 찾는 중...")
            if not find_and_open_room():
                return False
            print(f"[카카오] 창 찾음, 클릭 시도...")

            rooms = find_hwnd(ROOM_NAME)
            if rooms:
                hwnd = rooms[0][0]
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                x = (rect.left + rect.right) // 2
                y = rect.bottom - 50
                print(f"[카카오] 클릭 좌표: {x}, {y}")
                try:
                    pyautogui.click(x, y)
                except Exception as e:
                    print(f"[카카오] 클릭 실패 (무시): {e}")
                time.sleep(0.3)

            print(f"[카카오] 붙여넣기 시도...")
            pyperclip.copy(message)
            try:
                pyautogui.hotkey("ctrl", "v")
            except Exception as e:
                print(f"[카카오] hotkey 실패 (무시): {e}")
            time.sleep(0.2)
            try:
                pyautogui.press("enter")
            except Exception as e:
                print(f"[카카오] enter 실패 (무시): {e}")
            print(f"[카카오] 전송 완료: {message}")
            return True
        except Exception as e:
            print(f"[카카오] 전송 실패: {e}")
            return False


@app.route("/alert", methods=["POST"])
def alert():
    # 토큰 검증
    token = request.headers.get("X-Token")
    if token != SECRET_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.json
    boss = data.get("boss", "")
    alert_type = data.get("type", "")  # "5min" or "spawn"

    if alert_type == "5min":
        message = f"[{boss}] 5분 전 입니다."
    elif alert_type == "spawn":
        message = f"[{boss}] 젠 시간입니다."
    else:
        return jsonify({"ok": False, "error": "Invalid type"}), 400

    # 별도 스레드에서 전송 (응답 즉시 반환)
    threading.Thread(target=send_message, args=(message,), daemon=False).start()
    return jsonify({"ok": True})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "status": "running"})


if __name__ == "__main__":
    print(f"[카카오] 알림 서버 시작 (포트 5000)")
    print(f"[카카오] 채팅방: {ROOM_NAME}")
    print(f"[카카오] ngrok 실행 후 출력된 주소를 settings.json에 입력하세요")
    app.run(host="0.0.0.0", port=5000)
