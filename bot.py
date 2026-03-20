import discord
from discord.ext import commands
import os
import json
import asyncio
import tempfile
from datetime import datetime, timedelta
from dotenv import load_dotenv
import edge_tts
import gspread
from google.oauth2.service_account import Credentials

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

intents = discord.Intents.default()
intents.message_content = True

# 보스이름 -> asyncio.Task (개별 리젠 알림)
pending_tasks = {}

# 보스이름 -> {"respawn_at": datetime, "label": str}
boss_info = {}

# group_key(가장 빠른 보스이름) -> asyncio.Task (5분 전 묶음 알림)
group_warning_tasks = {}

CONFIG_FILE   = "boss_config.json"
SETTINGS_FILE = "settings.json"
RESPAWN_FILE  = "respawn_data.json"


# ────────── 설정 파일 (boss_config.json) ──────────

def load_config():
    """boss_config.json에서 보스별 알림 활성화 상태 로드 (없으면 전체 활성화)"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def is_enabled(boss_name):
    """보스 알림 활성화 여부 (기본값: True)"""
    return load_config().get(boss_name, True)


# ────────── 설정 파일 (settings.json) ──────────

def load_settings():
    """settings.json에서 전체 설정값 로드"""
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_setting(*keys, default=None):
    """settings.json에서 중첩 키 값 조회
    예) get_setting("discord", "voice_channel_id")
    """
    data = load_settings()
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data


def set_setting(value, *keys):
    """settings.json에서 중첩 키 값 저장
    예) set_setting(123456, "discord", "voice_channel_id")
    """
    settings = load_settings()
    target = settings
    for key in keys[:-1]:
        target = target.setdefault(key, {})
    target[keys[-1]] = value
    save_settings(settings)


PREFIX = get_setting("discord", "command_prefix", default="!")
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

SPREADSHEET_NAME = "보탐봇테스트"
SHEET_NAME = "참여율체크"
CREDENTIALS_FILE = "bsbot-428416-2282f2d345ef.json"


def get_sheet():
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=[
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    gc = gspread.authorize(creds)
    return gc.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)


def record_cut_to_sheet(boss_name):
    try:
        sheet = get_sheet()
        last_row_idx = len(sheet.get_all_values())  # 마지막 데이터 행 번호 (1-based)
        new_row_idx = last_row_idx + 1

        cb_range = {
            "sheetId": sheet.id,
            "startRowIndex": last_row_idx,
            "endRowIndex": last_row_idx + 1,
            "startColumnIndex": 2,
            "endColumnIndex": 44
        }

        # 새 행 삽입 (서식 상속 없이 빈 행)
        try:
            sheet.spreadsheet.batch_update({"requests": [
                {"insertDimension": {
                    "range": {
                        "sheetId": sheet.id,
                        "dimension": "ROWS",
                        "startIndex": last_row_idx,
                        "endIndex": last_row_idx + 1
                    },
                    "inheritFromBefore": False
                }},
                # 전체 행 서식 복사 (테두리, 글자 서식 등)
                {"copyPaste": {
                    "source": {
                        "sheetId": sheet.id,
                        "startRowIndex": last_row_idx - 1,
                        "endRowIndex": last_row_idx,
                        "startColumnIndex": 0,
                        "endColumnIndex": 44
                    },
                    "destination": {
                        "sheetId": sheet.id,
                        "startRowIndex": last_row_idx,
                        "endRowIndex": last_row_idx + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": 44
                    },
                    "pasteType": "PASTE_FORMAT"
                }},
                # B열 드롭박스 유효성 복사
                {"copyPaste": {
                    "source": {
                        "sheetId": sheet.id,
                        "startRowIndex": last_row_idx - 1,
                        "endRowIndex": last_row_idx,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2
                    },
                    "destination": {
                        "sheetId": sheet.id,
                        "startRowIndex": last_row_idx,
                        "endRowIndex": last_row_idx + 1,
                        "startColumnIndex": 1,
                        "endColumnIndex": 2
                    },
                    "pasteType": "PASTE_DATA_VALIDATION"
                }},
                # C~AR열 숫자 서식 초기화 (PASTE_FORMAT으로 TEXT 서식이 복사될 경우 방지)
                {"repeatCell": {
                    "range": cb_range,
                    "cell": {"userEnteredFormat": {"numberFormat": {}}},
                    "fields": "userEnteredFormat.numberFormat"
                }},
                # C~AR열 체크박스 데이터 유효성 적용
                {"setDataValidation": {
                    "range": cb_range,
                    "rule": {
                        "condition": {"type": "BOOLEAN"},
                        "strict": True
                    }
                }}
            ]})
            print(f"[시트] 행 삽입 + 유효성 적용 완료 (행 {new_row_idx})")
        except Exception as e:
            print(f"[시트] 행 삽입 실패: {e}")
            raise

        # A열: 오늘 날짜, B열: 보스명 (C~AR은 체크박스 기본값 미체크)
        try:
            sheet.update([[datetime.now().strftime("%m/%d")]], f"A{new_row_idx}", value_input_option="USER_ENTERED")
            sheet.update([[boss_name]], f"B{new_row_idx}", value_input_option="USER_ENTERED")
            print(f"[시트] 값 입력 완료")
        except Exception as e:
            print(f"[시트] 값 입력 실패: {e}")
            raise

        return True
    except Exception as e:
        print(f"[시트 기록 오류] {e}")
        return False

ALLOWED_ROLE = "운영진"


@bot.check
async def only_staff(ctx):
    if any(r.name == ALLOWED_ROLE for r in ctx.author.roles):
        return True
    await ctx.send("❌ 운영진만 사용할 수 있는 명령어입니다.")
    return False


# ────────── 리젠 데이터 파일 (respawn_data.json) ──────────

def save_respawn_entry(boss_name, target_dt, label, channel_id):
    """보스 알림 등록 시 파일에 저장"""
    data = {}
    if os.path.exists(RESPAWN_FILE):
        with open(RESPAWN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    data[boss_name] = {
        "respawn_at": target_dt.isoformat(),
        "label": label,
        "channel_id": channel_id
    }
    with open(RESPAWN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_respawn_entry(boss_name):
    """보스 알림 완료/취소 시 파일에서 삭제"""
    if not os.path.exists(RESPAWN_FILE):
        return
    with open(RESPAWN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop(boss_name, None)
    with open(RESPAWN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_respawn_data():
    """저장된 전체 리젠 데이터 로드"""
    if not os.path.exists(RESPAWN_FILE):
        return {}
    with open(RESPAWN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ────────── bosses.txt ──────────

def load_bosses():
    bosses = {}
    with open("bosses.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) == 3:
                name = parts[1].strip()
                minutes = int(parts[2].strip())
                bosses[name] = minutes
    return bosses


def load_bosses_by_chapter():
    """챕터별로 그룹화된 보스 목록 반환 {chapter: [(name, minutes), ...]}"""
    from collections import OrderedDict
    chapters = OrderedDict()
    with open("bosses.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) == 3:
                chapter = parts[0].strip()
                name = parts[1].strip()
                minutes = int(parts[2].strip())
                chapters.setdefault(chapter, []).append((name, minutes))
    return chapters


def get_boss_chapter(boss_name):
    """보스 이름으로 챕터 번호 반환 (없으면 None)"""
    with open("bosses.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) == 3 and parts[1].strip() == boss_name:
                return parts[0].strip()
    return None


def find_boss(name, bosses):
    if name in bosses:
        return name
    for boss in bosses:
        if name in boss or boss in name:
            return boss
    return None


# ────────── 유틸 ──────────

def format_duration(minutes):
    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours}시간 {mins}분"
    elif hours:
        return f"{hours}시간"
    else:
        return f"{mins}분"


def format_remaining(target_dt):
    total_secs = max(0, int((target_dt - datetime.now()).total_seconds()))
    r_hours = total_secs // 3600
    r_mins = (total_secs % 3600) // 60
    r_secs = total_secs % 60
    if r_hours:
        return f"{r_hours}시간 {r_mins}분 {r_secs}초"
    else:
        return f"{r_mins}분 {r_secs}초"


def parse_time(time_str, must_be_future=False):
    if len(time_str) == 4 and time_str.isdigit():
        time_str = time_str[:2] + ":" + time_str[2:]
    now = datetime.now()
    dt = datetime.strptime(time_str, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day
    )
    if must_be_future and dt <= now:
        dt += timedelta(days=1)
    elif not must_be_future and dt > now:
        dt -= timedelta(days=1)
    return dt


# ────────── UI: 컷 버튼 ──────────

class CutButton(discord.ui.View):
    def __init__(self, boss_name, respawn_minutes, channel):
        super().__init__(timeout=None)
        self.boss_name = boss_name
        self.respawn_minutes = respawn_minutes
        self.channel = channel
        self.processing = False

    @discord.ui.button(label="⚔️ 컷!", style=discord.ButtonStyle.danger)
    async def cut(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.processing:
            await interaction.response.defer()
            return
        self.processing = True

        now = datetime.now()
        next_respawn_dt = now + timedelta(minutes=self.respawn_minutes)

        register_alert(self.channel, self.boss_name, next_respawn_dt, "처치 기반")

        button.disabled = True
        button.label = f"✅ {interaction.user.display_name} 컷"
        await interaction.response.edit_message(view=self)

        # 구글 시트에 기록
        loop = asyncio.get_event_loop()
        sheet_ok = await loop.run_in_executor(None, record_cut_to_sheet, self.boss_name)

        embed = discord.Embed(
            title="💀 컷 처리 완료",
            description=f"**{self.boss_name}** 처치 완료!",
            color=discord.Color.green()
        )
        embed.add_field(name="처치 시각", value=now.strftime("%H:%M"), inline=True)
        embed.add_field(name="다음 리젠", value=next_respawn_dt.strftime("%H:%M"), inline=True)
        embed.add_field(name="리젠 시간", value=format_duration(self.respawn_minutes), inline=True)
        if sheet_ok:
            embed.set_footer(text="✅ 시트 기록 완료")
        else:
            embed.set_footer(text="⚠️ 시트 기록 실패")
        await self.channel.send(embed=embed)


# ────────── UI: 알림 설정 토글 버튼 ──────────

def make_config_embed(bosses, config):
    embed = discord.Embed(
        title="🔔 보스 알림 설정",
        description="버튼을 눌러 알림을 켜고 끄세요.\n🟢 알림 ON  |  🔴 알림 OFF",
        color=discord.Color.blurple()
    )
    embed.set_footer(text="설정은 자동 저장됩니다")
    return embed


class BossToggleView(discord.ui.View):
    def __init__(self, bosses, config):
        super().__init__(timeout=300)
        self.bosses = bosses
        self.config = config
        self._build_buttons()

    def _build_buttons(self):
        self.clear_items()
        for boss_name in self.bosses:
            enabled = self.config.get(boss_name, True)
            btn = discord.ui.Button(
                label=f"{'🟢' if enabled else '🔴'} {boss_name}",
                style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary,
                custom_id=f"toggle_{boss_name}"
            )
            btn.callback = self._make_callback(boss_name)
            self.add_item(btn)

    def _make_callback(self, boss_name):
        async def callback(interaction: discord.Interaction):
            self.config[boss_name] = not self.config.get(boss_name, True)
            save_config(self.config)
            self._build_buttons()
            await interaction.response.edit_message(
                embed=make_config_embed(self.bosses, self.config),
                view=self
            )
        return callback


# ────────── 음성 알림 ──────────

async def play_tts(text_channel, text):
    """설정된 음성 채널에서 TTS 재생"""
    vc_id = get_setting("discord", "voice_channel_id")
    if not vc_id:
        return

    guild = text_channel.guild
    voice_channel = guild.get_channel(vc_id)
    if not voice_channel or not isinstance(voice_channel, discord.VoiceChannel):
        return

    tts_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tts_path = f.name
        communicate = edge_tts.Communicate(text=text, voice="ko-KR-SunHiNeural")
        await communicate.save(tts_path)

        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if vc and vc.is_connected():
            await vc.move_to(voice_channel)
        else:
            vc = await voice_channel.connect()

        future = asyncio.get_event_loop().create_future()

        def after_play(error):
            if tts_path and os.path.exists(tts_path):
                os.unlink(tts_path)
            asyncio.run_coroutine_threadsafe(vc.disconnect(), bot.loop)
            bot.loop.call_soon_threadsafe(future.set_result, None)

        vc.play(discord.FFmpegPCMAudio(tts_path), after=after_play)
        await future

    except Exception as e:
        print(f"[TTS 오류] {e}")
        if tts_path and os.path.exists(tts_path):
            os.unlink(tts_path)


# ────────── 알림 스케줄링 ──────────

async def schedule_notify(channel, boss_name, target_dt, label):
    # 5분 전 단독 알림
    warning_secs = (target_dt - timedelta(minutes=5) - datetime.now()).total_seconds()
    if warning_secs > 0:
        await asyncio.sleep(warning_secs)
        embed = discord.Embed(
            title="⚠️ 보스 리젠 5분 전!",
            description=f"**{boss_name}** 이(가) 5분 후 리젠됩니다!",
            color=discord.Color.yellow()
        )
        embed.add_field(name="젠 시각", value=target_dt.strftime("%H:%M"), inline=True)
        await channel.send("@here", embed=embed)
        await play_tts(channel, f"{boss_name} 5분 전 입니다.")

    remaining = (target_dt - datetime.now()).total_seconds()
    if remaining > 0:
        await asyncio.sleep(remaining)

    bosses = load_bosses()
    respawn_minutes = bosses.get(boss_name, 0)
    chapter = get_boss_chapter(boss_name)
    auto_renew = chapter in ("2", "3")

    embed = discord.Embed(
        title="⚔️ 보스 리젠 알림!",
        description=f"**{boss_name}** 이(가) 리젠되었습니다!",
        color=discord.Color.red()
    )
    embed.add_field(name="등록 방식", value=label, inline=True)
    embed.add_field(name="리젠 시각", value=target_dt.strftime("%H:%M"), inline=True)

    view = None if auto_renew else (CutButton(boss_name, respawn_minutes, channel) if respawn_minutes else None)
    await channel.send("@here", embed=embed, view=view)
    await play_tts(channel, f"{boss_name} 시간입니다.")

    pending_tasks.pop(boss_name, None)
    boss_info.pop(boss_name, None)
    delete_respawn_entry(boss_name)

    # 챕터 2/3 보스는 3초 후 자동 갱신
    if auto_renew and respawn_minutes:
        await asyncio.sleep(3)
        next_dt = target_dt + timedelta(minutes=respawn_minutes)
        register_alert(channel, boss_name, next_dt, "자동 갱신")
        embed_renew = discord.Embed(
            title="🔄 자동 갱신",
            description=f"**{boss_name}** 다음 리젠 알림이 자동 등록되었습니다.",
            color=discord.Color.blurple()
        )
        embed_renew.add_field(name="다음 젠 시각", value=next_dt.strftime("%H:%M"), inline=True)
        await channel.send(embed=embed_renew)


def compute_groups():
    active = [
        (name, boss_info[name]["respawn_at"])
        for name in boss_info
        if name in pending_tasks and not pending_tasks[name].done()
    ]
    active.sort(key=lambda x: x[1])

    groups = []
    if not active:
        return groups

    current_group = [active[0]]
    for item in active[1:]:
        if (item[1] - current_group[0][1]).total_seconds() <= 600:
            current_group.append(item)
        else:
            groups.append(current_group)
            current_group = [item]
    groups.append(current_group)

    return [g for g in groups if len(g) >= 2]


async def send_group_warning(channel, group):
    earliest_dt = group[0][1]
    warning_dt = earliest_dt - timedelta(minutes=5)
    remaining = (warning_dt - datetime.now()).total_seconds()

    if remaining > 0:
        await asyncio.sleep(remaining)

    active_group = [
        (name, dt) for name, dt in group
        if name in pending_tasks and not pending_tasks[name].done()
    ]
    if len(active_group) < 2:
        return

    names_str = "  →  ".join(f"**{name}**" for name, _ in active_group)
    embed = discord.Embed(
        title="⚠️ 보스 리젠 5분 전!",
        description=names_str,
        color=discord.Color.yellow()
    )
    time_range = f"{active_group[0][1].strftime('%H:%M')} ~ {active_group[-1][1].strftime('%H:%M')}"
    embed.add_field(name="리젠 예정 시각", value=time_range, inline=True)
    await channel.send("@here", embed=embed)

    names_tts = ", ".join(name for name, _ in active_group)
    await play_tts(channel, f"{names_tts} 5분 전 입니다.")


def recalculate_group_warnings(channel):
    for task in group_warning_tasks.values():
        task.cancel()
    group_warning_tasks.clear()

    for group in compute_groups():
        key = group[0][0]
        task = asyncio.create_task(send_group_warning(channel, group))
        group_warning_tasks[key] = task


def register_alert(channel, boss_name, target_dt, label):
    if boss_name in pending_tasks:
        pending_tasks[boss_name].cancel()

    boss_info[boss_name] = {"respawn_at": target_dt, "label": label}
    task = asyncio.create_task(schedule_notify(channel, boss_name, target_dt, label))
    pending_tasks[boss_name] = task

    save_respawn_entry(boss_name, target_dt, label, channel.id)
    recalculate_group_warnings(channel)


# ────────── 이벤트 ──────────

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    def is_staff(member):
        return any(r.name == ALLOWED_ROLE for r in member.roles)

    if message.content.strip() in ("명령어", "!명령어"):
        ctx = await bot.get_context(message)
        await show_commands(ctx)
        return

    if message.content.strip() in ("보스", "ㅄ"):
        if not is_staff(message.author):
            await message.channel.send("❌ 운영진만 사용할 수 있는 명령어입니다.")
            return
        ctx = await bot.get_context(message)
        await status(ctx)
        return

    # !보스명 시간 형식 처리 (예: !니드호그 15:30)
    content = message.content.strip()
    if content.startswith(PREFIX):
        parts = content[len(PREFIX):].split()
        if len(parts) == 2:
            boss_input, time_input = parts
            bosses = load_bosses()
            matched = find_boss(boss_input, bosses)
            if matched:
                if not is_staff(message.author):
                    await message.channel.send("❌ 운영진만 사용할 수 있는 명령어입니다.")
                    return
                ctx = await bot.get_context(message)
                try:
                    target_dt = parse_time(time_input, must_be_future=True)
                except ValueError:
                    await ctx.send("❌ 시간 형식이 올바르지 않습니다. 예) `!니드호그 15:30`")
                    return

                if not is_enabled(matched):
                    await ctx.send(f"🔴 **{matched}** 은(는) 알림이 비활성화되어 있습니다. `!알림설정`에서 켜주세요.")
                    return

                register_alert(ctx.channel, matched, target_dt, "수동 설정")

                embed = discord.Embed(
                    title="🕐 리젠 예약 완료",
                    description=f"**{matched}** 리젠 예상 시각이 등록되었습니다.",
                    color=discord.Color.purple()
                )
                embed.add_field(name="젠 시각", value=target_dt.strftime("%H:%M"), inline=True)
                embed.add_field(name="남은 시간", value=format_remaining(target_dt), inline=True)
                embed.set_footer(text="점검 후 수동 설정")
                await ctx.send(embed=embed)
                return

    await bot.process_commands(message)


@bot.event
async def on_ready():
    s = load_settings()
    prefix      = s.get("discord", {}).get("command_prefix", "!")
    alert_ch_id = s.get("discord", {}).get("alert_channel_id")
    voice_ch_id = s.get("discord", {}).get("voice_channel_id")
    print(f"✅ {bot.user} 봇이 준비되었습니다!")
    print(f"   prefix        : {prefix}")
    print(f"   alert_channel : {alert_ch_id or '미설정'}")
    print(f"   voice_channel : {voice_ch_id or '미설정'}")

    # ── 봇 재시작 시 저장된 리젠 알림 복구 ──
    data = load_respawn_data()
    if not data:
        return

    restored, missed = [], []

    for boss_name, entry in data.items():
        channel = bot.get_channel(entry["channel_id"])
        if not channel:
            continue

        target_dt = datetime.fromisoformat(entry["respawn_at"])
        label = entry["label"]
        now = datetime.now()

        if target_dt <= now:
            # 이미 리젠 시각이 지난 경우
            missed.append((boss_name, target_dt))
            delete_respawn_entry(boss_name)
        else:
            # 아직 리젠 전 → 알림 재등록 (기존 태스크 있으면 취소 후 재생성)
            if boss_name in pending_tasks:
                pending_tasks[boss_name].cancel()
            boss_info[boss_name] = {"respawn_at": target_dt, "label": label}
            task = asyncio.create_task(schedule_notify(channel, boss_name, target_dt, label))
            pending_tasks[boss_name] = task
            recalculate_group_warnings(channel)
            restored.append(boss_name)

    # 복구 결과 채널에 안내
    for boss_name, entry in data.items():
        channel = bot.get_channel(entry["channel_id"])
        if not channel:
            continue

        if restored or missed:
            embed = discord.Embed(title="🔄 봇 재시작 - 알림 복구", color=discord.Color.blurple())
            if restored:
                embed.add_field(name="✅ 복구 완료", value="\n".join(restored), inline=False)
            if missed:
                missed_str = "\n".join(
                    f"{name} (리젠 시각: {dt.strftime('%H:%M')})" for name, dt in missed
                )
                embed.add_field(name="⚠️ 재시작 중 리젠 (놓침)", value=missed_str, inline=False)
            await channel.send(embed=embed)
            break  # 채널 하나에만 전송


# ────────── 명령어 ──────────

@bot.command(name="킬")
async def kill_boss(ctx, boss_name: str, kill_time_str: str = None):
    bosses = load_bosses()
    matched = find_boss(boss_name, bosses)

    if not matched:
        await ctx.send(f"❌ `{boss_name}` 보스를 찾을 수 없습니다. `!보스목록`으로 확인해주세요.")
        return

    if not is_enabled(matched):
        await ctx.send(f"🔴 **{matched}** 은(는) 알림이 비활성화되어 있습니다. `!알림설정`에서 켜주세요.")
        return

    if kill_time_str:
        try:
            kill_dt = parse_time(kill_time_str, must_be_future=False)
        except ValueError:
            await ctx.send("❌ 시간 형식이 올바르지 않습니다. 예) `!킬 니드호그 14:30`")
            return
    else:
        kill_dt = datetime.now()

    respawn_minutes = bosses[matched]
    target_dt = kill_dt + timedelta(minutes=respawn_minutes)

    register_alert(ctx.channel, matched, target_dt, "처치 기반")

    embed = discord.Embed(
        title="💀 처치 기록 완료",
        description=f"**{matched}** 처치 기록이 등록되었습니다.",
        color=discord.Color.green()
    )
    embed.add_field(name="처치 시각", value=kill_dt.strftime("%H:%M"), inline=True)
    embed.add_field(name="리젠 예정", value=target_dt.strftime("%H:%M"), inline=True)
    embed.add_field(name="리젠 시간", value=format_duration(respawn_minutes), inline=True)
    await ctx.send(embed=embed)


@bot.command(name="젠")
async def set_respawn(ctx, boss_name: str, respawn_time_str: str):
    bosses = load_bosses()
    matched = find_boss(boss_name, bosses)

    if not matched:
        await ctx.send(f"❌ `{boss_name}` 보스를 찾을 수 없습니다. `!보스목록`으로 확인해주세요.")
        return

    if not is_enabled(matched):
        await ctx.send(f"🔴 **{matched}** 은(는) 알림이 비활성화되어 있습니다. `!알림설정`에서 켜주세요.")
        return

    try:
        target_dt = parse_time(respawn_time_str, must_be_future=True)
    except ValueError:
        await ctx.send("❌ 시간 형식이 올바르지 않습니다. 예) `!젠 니드호그 15:30`")
        return

    register_alert(ctx.channel, matched, target_dt, "수동 설정")

    embed = discord.Embed(
        title="🕐 리젠 예약 완료",
        description=f"**{matched}** 리젠 예상 시각이 등록되었습니다.",
        color=discord.Color.purple()
    )
    embed.add_field(name="리젠 예정 시각", value=target_dt.strftime("%H:%M"), inline=True)
    embed.add_field(name="남은 시간", value=format_remaining(target_dt), inline=True)
    embed.set_footer(text="점검 후 수동 설정")
    await ctx.send(embed=embed)


@bot.command(name="현황")
async def status(ctx):
    active = {k: v for k, v in pending_tasks.items() if not v.done()}

    if not active:
        await ctx.send("⚠️ 현재 대기 중인 보스 알림이 없습니다.")
        return

    sorted_bosses = sorted(
        [name for name in active if name in boss_info],
        key=lambda name: boss_info[name]["respawn_at"]
    )

    urgent = []
    normal = []

    for i, boss_name in enumerate(sorted_bosses, start=1):
        target_dt = boss_info[boss_name]["respawn_at"]
        remaining_secs = max(0, (target_dt - datetime.now()).total_seconds())
        if remaining_secs <= 600:
            urgent.append((i, boss_name))
        else:
            normal.append((i, boss_name))

    lines = []

    if urgent:
        lines.append("🚨 **10분 이내 리젠**")
        lines.append("  →  ".join(f"**{i}. {name}**" for i, name in urgent))
        lines.append("")

    if normal:
        for i, boss_name in normal:
            info = boss_info[boss_name]
            target_dt = info["respawn_at"]
            label = info["label"]
            lines.append(
                f"`{i}.` **{boss_name}**  ⏱ {format_remaining(target_dt)}  |  🕐 {target_dt.strftime('%H:%M')}  |  {label}"
            )

    # 비활성화 보스 목록 추가
    bosses = load_bosses()
    config = load_config()
    disabled = [name for name in bosses if not config.get(name, True)]
    if disabled:
        lines.append("")
        lines.append("🔴 **알림 비활성화**  " + "  |  ".join(disabled))

    embed = discord.Embed(
        title="⏰ 리젠 대기 현황",
        description="\n".join(lines),
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)


@bot.command(name="보스목록")
async def boss_list(ctx):
    chapters = load_bosses_by_chapter()
    config = load_config()

    chapter_labels = {
        "2": "챕터 2", "3": "챕터 3", "4": "챕터 4",
        "5": "챕터 5", "6": "챕터 6", "7": "챕터 7",
        "11": "챕터 11 (던전)", "12": "챕터 12 (절대자)"
    }

    embeds = []
    current_embed = discord.Embed(title="📋 오딘 보스 목록", color=discord.Color.blue())
    field_count = 0

    for chapter, boss_list_items in chapters.items():
        label = chapter_labels.get(chapter, f"챕터 {chapter}")

        # 챕터 구분선 필드 추가 시 25개 초과 여부 확인
        if field_count + len(boss_list_items) + 1 > 25:
            embeds.append(current_embed)
            current_embed = discord.Embed(title="📋 오딘 보스 목록 (계속)", color=discord.Color.blue())
            field_count = 0

        current_embed.add_field(name=f"── {label} ──", value="\u200b", inline=False)
        field_count += 1

        for name, minutes in boss_list_items:
            if field_count >= 25:
                embeds.append(current_embed)
                current_embed = discord.Embed(title="📋 오딘 보스 목록 (계속)", color=discord.Color.blue())
                field_count = 0

            enabled = config.get(name, True)
            status_icon = "🟢" if enabled else "🔴"
            current_embed.add_field(
                name=f"{status_icon} {name}",
                value=format_duration(minutes),
                inline=True
            )
            field_count += 1

    current_embed.set_footer(text="🟢 알림 ON  |  🔴 알림 OFF  |  !알림설정 으로 변경")
    embeds.append(current_embed)

    for embed in embeds:
        await ctx.send(embed=embed)


@bot.command(name="알림설정")
async def notify_settings(ctx):
    bosses = load_bosses()
    config = load_config()
    embed = make_config_embed(bosses, config)
    view = BossToggleView(bosses, config)
    await ctx.send(embed=embed, view=view)


@bot.command(name="음성채널")
async def set_voice_channel(ctx):
    """현재 접속 중인 음성 채널을 알림 채널로 설정
    사용법: !음성채널
    """
    if not ctx.author.voice or not ctx.author.voice.channel:
        vc_id = get_setting("discord", "voice_channel_id")
        if vc_id:
            vc = ctx.guild.get_channel(vc_id)
            vc_name = vc.name if vc else "알 수 없음 (채널 삭제됨)"
            await ctx.send(f"🔊 현재 설정된 음성 채널: **{vc_name}**\n음성 채널에 입장 후 `!음성채널` 을 입력하면 변경됩니다.")
        else:
            await ctx.send("❌ 음성 채널에 먼저 입장한 뒤 `!음성채널` 을 입력해주세요.")
        return

    voice_channel = ctx.author.voice.channel
    set_setting(voice_channel.id, "discord", "voice_channel_id")

    await ctx.send(f"🔊 음성 알림 채널이 **{voice_channel.name}** 으로 설정되었습니다.")


@bot.command(name="음성채널해제")
async def unset_voice_channel(ctx):
    """음성 알림 채널 설정 해제"""
    if not get_setting("discord", "voice_channel_id"):
        await ctx.send("❌ 설정된 음성 채널이 없습니다.")
        return

    set_setting(None, "discord", "voice_channel_id")
    await ctx.send("🔇 음성 알림이 해제되었습니다.")


@bot.command(name="취소")
async def cancel_boss(ctx, *, boss_name: str):
    bosses = load_bosses()
    matched = find_boss(boss_name, bosses)

    if not matched or matched not in pending_tasks or pending_tasks[matched].done():
        await ctx.send(f"❌ `{boss_name}`에 대한 대기 중인 알림이 없습니다.")
        return

    pending_tasks[matched].cancel()
    pending_tasks.pop(matched, None)
    boss_info.pop(matched, None)
    delete_respawn_entry(matched)

    recalculate_group_warnings(ctx.channel)

    await ctx.send(f"✅ **{matched}** 알림이 취소되었습니다.")


@bot.command(name="핑")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! ({round(bot.latency * 1000)}ms)")


@bot.command(name="보스초기화", aliases=["초기화", "리셋"])
async def reset_all(ctx):
    count = len([t for t in pending_tasks.values() if not t.done()])

    for task in pending_tasks.values():
        task.cancel()
    for task in group_warning_tasks.values():
        task.cancel()

    pending_tasks.clear()
    boss_info.clear()
    group_warning_tasks.clear()

    if os.path.exists(RESPAWN_FILE):
        with open(RESPAWN_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

    embed = discord.Embed(
        title="🗑️ 초기화 완료",
        description=f"등록된 보스 알림 **{count}개**가 모두 제거되었습니다.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)


async def show_commands(ctx):
    embed = discord.Embed(
        title="📖 명령어 목록",
        description="사용 가능한 명령어 안내입니다.",
        color=discord.Color.green()
    )
    embed.add_field(
        name="⚔️ 보스 등록",
        value=(
            "`!킬 보스명` — 현재 시각 기준 처치 등록\n"
            "`!킬 보스명 14:30` — 처치 시각 지정 등록\n"
            "`!젠 보스명 15:30` — 리젠 시각 직접 지정\n"
            "`!보스명 15:30` — 리젠 시각 직접 지정 (단축)"
        ),
        inline=False
    )
    embed.add_field(
        name="📋 조회",
        value=(
            "`보스` 또는 `ㅄ` — 현재 대기 중인 보스 현황\n"
            "`!보스목록` — 전체 보스 및 리젠 시간 목록"
        ),
        inline=False
    )
    embed.add_field(
        name="🔔 알림 설정",
        value=(
            "`!알림설정` — 보스별 알림 ON/OFF 설정\n"
            "`!취소 보스명` — 등록된 보스 알림 취소\n"
            "`!초기화` / `!리셋` / `!보스초기화` — 등록된 보스 알림 전체 제거"
        ),
        inline=False
    )
    embed.add_field(
        name="🔊 음성 채널",
        value=(
            "`!음성채널` — 현재 입장 중인 음성 채널을 TTS 채널로 설정\n"
            "`!음성채널해제` — TTS 음성 알림 해제"
        ),
        inline=False
    )
    embed.set_footer(text="운영진 역할이 있어야 명령어를 사용할 수 있습니다.")
    await ctx.send(embed=embed)


bot.run(os.getenv("DISCORD_TOKEN"))
