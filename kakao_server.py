"""
카카오톡 알림 서버 (Windows 로컬 PC 실행용)

[설치]
pip install flask pyautogui pygetwindow pyperclip

[실행]
python kakao_server.py

[ngrok 터널링]
ngrok http 5000
→ 출력된 https://xxxx.ngrok.io 주소를 settings_{guild_id}.json의 kakao.server_url에 입력

[멀티 서버 지원]
요청 body에 "room" 필드를 포함하면 해당 채팅방으로 전송.
없으면 DEFAULT_ROOM으로 전송.
"""

from flask import Flask, request, jsonify
import pyautogui
import pyperclip
import threading
import time
import ctypes
import ctypes.wintypes

app = Flask(__name__)

DEFAULT_ROOM  = "해운대Z-보스타임"   # room 미지정 시 기본 채팅방
SECRET_TOKEN  = "bsbot-kakao-token"  # 리눅스 봇과 동일하게 설정

send_lock = threading.Lock()


def find_hwnd(title_keyword):
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
    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.5)


def find_and_open_room(room_name):
    """채팅방 창 찾기 (열려있으면 활성화, 없으면 메인창에서 검색)"""
    rooms = find_hwnd(room_name)
    if rooms:
        activate_hwnd(rooms[0][0])
        return True

    kakao_wins = find_hwnd("카카오톡")
    if not kakao_wins:
        print(f"[카카오] 카카오톡 창을 찾을 수 없습니다.")
        return False

    activate_hwnd(kakao_wins[0][0])
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.4)
    pyperclip.copy(room_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(0.8)
    return True


def send_message(message, room_name=None):
    """카카오톡 채팅방에 메시지 전송"""
    if room_name is None:
        room_name = DEFAULT_ROOM
    with send_lock:
        try:
            if not find_and_open_room(room_name):
                return False

            rooms = find_hwnd(room_name)
            if rooms:
                hwnd = rooms[0][0]
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                x = (rect.left + rect.right) // 2
                y = rect.bottom - 50
                try:
                    pyautogui.click(x, y)
                except Exception:
                    pass
                time.sleep(0.3)
            else:
                # 별도 창 없이 메인 창에 열린 경우 - 입력창 클릭
                time.sleep(0.3)
                kakao_wins = find_hwnd("카카오톡")
                if kakao_wins:
                    hwnd = kakao_wins[0][0]
                    rect = ctypes.wintypes.RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    # 오른쪽 패널 하단 입력창 위치 클릭
                    x = rect.left + int(w * 0.65)
                    y = rect.bottom - 60
                    try:
                        pyautogui.click(x, y)
                    except Exception:
                        pass
                    time.sleep(0.3)

            pyperclip.copy(message)
            try:
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                pass
            time.sleep(0.2)
            try:
                pyautogui.press("enter")
            except Exception:
                pass
            print(f"[카카오] 전송 완료 → [{room_name}]: {message[:30]}...")
            return True
        except Exception as e:
            print(f"[카카오] 전송 실패: {e}")
            return False


@app.route("/alert", methods=["POST"])
def alert():
    token = request.headers.get("X-Token")
    if token != SECRET_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data       = request.json
    boss       = data.get("boss", "")
    alert_type = data.get("type", "")
    room       = data.get("room") or DEFAULT_ROOM  # 서버별 채팅방
    print(f"[카카오] /alert 수신: boss={boss}, type={alert_type}, room_in_body={data.get('room')!r}, room_used={room}")

    if alert_type == "5min":
        message = f"[ 츄츄봇 - 보스알림 ]\n[{boss}] 5분 전 입니다."
    elif alert_type == "spawn":
        message = f"[ 츄츄봇 - 보스알림 ]\n[{boss}] 젠 시간입니다."
    else:
        return jsonify({"ok": False, "error": "Invalid type"}), 400

    threading.Thread(target=send_message, args=(message, room), daemon=False).start()
    return jsonify({"ok": True})


@app.route("/message", methods=["POST"])
def message_route():
    token = request.headers.get("X-Token")
    if token != SECRET_TOKEN:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.json
    msg  = data.get("message", "")
    room = data.get("room") or DEFAULT_ROOM  # 서버별 채팅방

    if not msg:
        return jsonify({"ok": False, "error": "No message"}), 400

    threading.Thread(target=send_message, args=(msg, room), daemon=False).start()
    return jsonify({"ok": True})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "status": "running"})


if __name__ == "__main__":
    print(f"[카카오] 알림 서버 시작 (포트 5000)")
    print(f"[카카오] 기본 채팅방: {DEFAULT_ROOM}")
    print(f"[카카오] room 파라미터로 서버별 채팅방 지정 가능")
    app.run(host="0.0.0.0", port=5000)
