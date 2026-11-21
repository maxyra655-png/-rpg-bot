import asyncio
import html
import json
import os
import random
import time
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATA_FILE = Path("crmp_russia_data.json")
OWNER_ID = 5516435343

SHIFT_COOLDOWN = 60
CRIME_COOLDOWN = 90
DAILY_COOLDOWN = 86400
RAID_COOLDOWN = 120

ADMIN_RANKS = {
    0: "Игрок",
    1: "Младший администратор (1 ранг)",
    2: "Администратор (2 ранг)",
    3: "Старший администратор (3 ранг)",
    4: "Заместитель главного администратора (4 ранг)",
    5: "Создатель проекта (5 ранг)",
}

CITIES = {
    "arzamas": "🏙 Арзамас",
    "lytkarino": "🏭 Лыткарино",
    "yuzhny": "🌊 Южный",
    "batyrevo": "🏡 Батырево",
    "rublevka": "💎 Рублёвка",
}

FACTIONS = {
    "none": {"name": "Гражданский", "type": "civil", "min_lvl": 1, "pay": (120, 220)},
    "courier": {"name": "Служба доставки", "type": "civil", "min_lvl": 1, "pay": (200, 320)},
    "trucker": {"name": "Дальнобойщики", "type": "civil", "min_lvl": 2, "pay": (320, 500)},
    "mechanic": {"name": "СТО / Механики", "type": "civil", "min_lvl": 2, "pay": (300, 460)},
    "dps": {"name": "ГИБДД / ДПС", "type": "gos", "min_lvl": 3, "pay": (400, 620)},
    "pps": {"name": "УМВД / ППС", "type": "gos", "min_lvl": 3, "pay": (420, 650)},
    "mchs": {"name": "МЧС России", "type": "gos", "min_lvl": 2, "pay": (360, 550)},
    "fsb": {"name": "ФСБ России", "type": "gos", "min_lvl": 5, "pay": (550, 820)},
    "opg_sun": {"name": "ОПГ «Солнцевские»", "type": "opg", "min_lvl": 3, "pay": (450, 720)},
    "opg_orekh": {"name": "ОПГ «Ореховские»", "type": "opg", "min_lvl": 3, "pay": (450, 720)},
}

DISGUISES = {
    "off": "Без маскировки",
    "civil": "Гражданский",
    "opg": "Участник ОПГ",
    "dps": "Сотрудник ДПС",
}

CARS = {
    "none": {"name": "Пешком / Общественный транспорт", "price": 0, "escape": 0},
    "vaz2107": {"name": "ВАЗ-2107", "price": 1500, "escape": 8},
    "prior": {"name": "Lada Priora", "price": 4500, "escape": 16},
    "m5e60": {"name": "BMW M5 E60", "price": 14000, "escape": 28},
    "g63": {"name": "Mercedes-AMG G63", "price": 26000, "escape": 36},
}

HOUSES = {
    "none": {"name": "Нет прописки", "price": 0, "pay_bonus": 0},
    "room": {"name": "Комната в общежитии", "price": 2500, "pay_bonus": 40},
    "flat_arz": {"name": "Квартира в Арзамасе", "price": 8000, "pay_bonus": 100},
    "house_bat": {"name": "Коттедж в Батырево", "price": 18000, "pay_bonus": 180},
    "villa_rub": {"name": "Особняк на Рублёвке", "price": 38000, "pay_bonus": 320},
}

users: dict[str, dict] = {}
faction_apps: dict[str, dict] = {}


def normalize_player(p: dict, tg_id: int) -> dict:
    p["tg_id"] = int(tg_id)
    if not p.get("game_id"):
        p["game_id"] = _generate_game_id()
    p.setdefault("name", f"Игрок_{tg_id}")
    p.setdefault("money", 1000)
    p.setdefault("lvl", 1)
    p.setdefault("xp", 0)
    p.setdefault("faction", "none")
    p.setdefault("rank", 1)
    p.setdefault("leader_of", None)
    p.setdefault("admin_rank", 0)
    p.setdefault("is_media", False)
    p.setdefault("disguise", "off")
    p.setdefault("car", "none")
    p.setdefault("house", "none")
    p.setdefault("city", "arzamas")
    p.setdefault("wanted", 0)
    p.setdefault("banned", False)
    p.setdefault("ban_reason", "")
    p.setdefault("last_shift", 0.0)
    p.setdefault("last_crime", 0.0)
    p.setdefault("last_daily", 0.0)
    p.setdefault("last_raid", 0.0)

    if p.get("faction") not in FACTIONS:
        p["faction"] = "none"
    if p.get("car") not in CARS:
        p["car"] = "none"
    if p.get("house") not in HOUSES:
        p["house"] = "none"
    if p.get("city") not in CITIES:
        p["city"] = "arzamas"
    if p.get("disguise") not in DISGUISES:
        p["disguise"] = "off"

    p["money"] = max(0, int(p.get("money", 0)))
    p["lvl"] = max(1, int(p.get("lvl", 1)))
    p["xp"] = max(0, int(p.get("xp", 0)))
    p["wanted"] = max(0, min(5, int(p.get("wanted", 0))))
    p["admin_rank"] = max(0, min(5, int(p.get("admin_rank", 0))))
    p["is_media"] = bool(p.get("is_media", False))
    p["banned"] = bool(p.get("banned", False))
    p["ban_reason"] = str(p.get("ban_reason") or "")

    if p.get("leader_of") == p["faction"] and p["faction"] != "none":
        p["rank"] = 10
    else:
        if p.get("leader_of") and p["leader_of"] != p["faction"]:
            p["leader_of"] = None
        r = int(p.get("rank", 1))
        p["rank"] = max(1, min(9 if p["faction"] != "none" else 1, r))

    if p["faction"] != "fsb":
        p["disguise"] = "off"

    if is_owner(tg_id):
        p["admin_rank"] = 5

    return p


def _generate_game_id() -> int:
    used = {int(u.get("game_id", 0)) for u in users.values() if str(u.get("game_id", "")).isdigit()}
    while True:
        candidate = random.randint(1000, 99999)
        if candidate not in used:
            return candidate


def load_state() -> None:
    users.clear()
    faction_apps.clear()
    if not DATA_FILE.exists():
        return
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return

    if isinstance(raw, dict) and "users" in raw and isinstance(raw["users"], dict):
        raw_users = raw["users"]
        raw_apps = raw.get("faction_apps") if isinstance(raw.get("faction_apps"), dict) else {}
    elif isinstance(raw, dict):
        raw_users = raw
        raw_apps = {}
    else:
        raw_users = {}
        raw_apps = {}

    for k, v in raw_users.items():
        if not isinstance(v, dict):
            continue
        try:
            tg_id = int(v.get("tg_id") or k)
        except ValueError:
            continue
        users[str(tg_id)] = normalize_player(dict(v), tg_id)

    for aid, app in raw_apps.items():
        if isinstance(app, dict):
            faction_apps[str(aid)] = dict(app)


def save_state() -> None:
    payload = {
        "users": users,
        "faction_apps": faction_apps,
    }
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_owner(user_id: int | None) -> bool:
    return bool(user_id) and int(user_id) == OWNER_ID


def get_admin_rank(user_id: int | None) -> int:
    if not user_id:
        return 0
    if is_owner(user_id):
        return 5
    u = users.get(str(user_id))
    if not u:
        return 0
    try:
        tg_id = int(u.get("tg_id") or user_id)
    except ValueError:
        tg_id = user_id
    normalize_player(u, tg_id)
    return int(u.get("admin_rank", 0))


def is_admin(user_id: int | None, min_rank: int = 1) -> bool:
    return get_admin_rank(user_id) >= min_rank


def is_media(user_id: int | None) -> bool:
    if not user_id:
        return False
    if is_owner(user_id):
        return True
    u = users.get(str(user_id))
    return bool(u and u.get("is_media"))


def is_leader(user_id: int | None) -> bool:
    if not user_id:
        return False
    u = users.get(str(user_id))
    if not u:
        return False
    lof = u.get("leader_of")
    return bool(lof and lof != "none" and u.get("faction") == lof)


def is_fsb(user_id: int | None) -> bool:
    if not user_id:
        return False
    u = users.get(str(user_id))
    return bool(u and u.get("faction") == "fsb")


def is_banned(p: dict | None) -> bool:
    return bool(p and p.get("banned"))


def get_player(user_id: int, full_name: str | None = None) -> dict:
    key = str(user_id)
    p = users.get(key)
    if not p:
        p = normalize_player({"name": full_name or f"Игрок_{user_id}"}, user_id)
        users[key] = p
        save_state()
    else:
        if full_name and full_name.strip():
            p["name"] = full_name.strip()
        normalize_player(p, user_id)
    return p


def find_by_game_id(game_id: int) -> dict | None:
    for k, u in users.items():
        if int(u.get("game_id", -1)) == int(game_id):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                tg_id = 0
            if tg_id:
                normalize_player(u, tg_id)
            return u
    return None


def add_xp(p: dict, amount: int) -> bool:
    p["xp"] += amount
    up = False
    while p["xp"] >= p["lvl"] * 120:
        p["xp"] -= p["lvl"] * 120
        p["lvl"] += 1
        up = True
    return up


def get_roles_badges(p: dict) -> list[str]:
    badges: list[str] = []
    tg_id = p.get("tg_id")
    arank = get_admin_rank(tg_id)
    if is_owner(tg_id):
        badges.append("Создатель (5)")
    elif arank > 0:
        badges.append(f"Админ {arank} ур.")
    if p.get("is_media"):
        badges.append("Медиа")
    if p.get("leader_of") and p.get("leader_of") != "none" and p.get("faction") == p.get("leader_of"):
        badges.append(f"Лидер {FACTIONS[p['leader_of']]['name']}")
    return badges


def format_passport(p: dict) -> str:
    fac = FACTIONS.get(p["faction"], FACTIONS["none"])
    car = CARS.get(p["car"], CARS["none"])
    house = HOUSES.get(p["house"], HOUSES["none"])
    city = CITIES.get(p["city"], CITIES["arzamas"])
    stars = "⭐" * p["wanted"] if p["wanted"] > 0 else "Чист"
    need_xp = p["lvl"] * 120
    badges = get_roles_badges(p)
    role_line = f"🎖 Должности: **{', '.join(badges)}**\n" if badges else ""
    mask_line = ""
    if p.get("faction") == "fsb" and p.get("disguise", "off") != "off":
        mask_line = f"🎭 Маскировка: **{DISGUISES[p['disguise']]}**\n"

    if p.get("leader_of") == p["faction"] and p["faction"] != "none":
        rank_val = 10
    elif p["faction"] == "none":
        rank_val = 0
    else:
        rank_val = max(1, min(9, int(p.get("rank", 1))))

    return (
        f"🪪 **Паспорт гражданина РФ**\n"
        f"{role_line}"
        f"👤 Имя: **{p['name']}** | 🆔 Игровой ID: **`{p['game_id']}`**\n\n"
        f"💵 Наличные: **{p['money']} ₽**\n"
        f"🎖 Уровень: **{p['lvl']}** (`{p['xp']}/{need_xp} XP`)\n"
        f"🏛 Организация: **{fac['name']}** (Ранг: `{rank_val}/10`)\n"
        f"{mask_line}"
        f"🚘 Транспорт: **{car['name']}**\n"
        f"🏠 Прописка: **{house['name']}**\n"
        f"📍 Город: **{city}**\n"
        f"🚨 Розыск: **{stars}**"
    )


def format_dossier(p: dict) -> str:
    fac = FACTIONS.get(p["faction"], FACTIONS["none"])
    car = CARS.get(p["car"], CARS["none"])
    house = HOUSES.get(p["house"], HOUSES["none"])
    city = CITIES.get(p["city"], CITIES["arzamas"])
    badges = ", ".join(get_roles_badges(p)) or "Нет"
    ban_status = f"Забанен ({p.get('ban_reason') or 'без причины'})" if p.get("banned") else "Нет"
    rank_val = 10 if (p.get("leader_of") == p["faction"] and p["faction"] != "none") else (0 if p["faction"] == "none" else int(p.get("rank", 1)))
    return (
        f"📁 **Досье игрока #{p['game_id']}**\n"
        f"👤 Имя: **{p['name']}** | TG ID: `{p['tg_id']}`\n"
        f"🎖 Роли: **{badges}**\n"
        f"🚫 Бан: **{ban_status}**\n"
        f"💵 Баланс: **{p['money']} ₽** | 🎚 Ур.: **{p['lvl']}** (`{p['xp']}/{p['lvl']*120} XP`)\n"
        f"🏛 Фракция: **{fac['name']}** (`{rank_val}/10`)\n"
        f"🚘 Авто: **{car['name']}** | 🏠 Жильё: **{house['name']}**\n"
        f"📍 Город: **{city}** | ⭐ Розыск: **{p['wanted']}/5**"
    )


def main_kb(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🪪 Паспорт", callback_data="m_passport"),
            InlineKeyboardButton(text="🗺 Города", callback_data="m_cities"),
        ],
        [
            InlineKeyboardButton(text="💼 Работа и фракции", callback_data="m_work"),
            InlineKeyboardButton(text="🔫 Криминал", callback_data="m_crime"),
        ],
        [
            InlineKeyboardButton(text="🚗 Автосалон", callback_data="m_cars"),
            InlineKeyboardButton(text="🏠 Недвижимость", callback_data="m_houses"),
        ],
        [
            InlineKeyboardButton(text="🎁 Бонус", callback_data="m_daily"),
            InlineKeyboardButton(text="🏆 Топ-10", callback_data="m_top"),
        ],
    ]
    extra: list[InlineKeyboardButton] = []
    if is_leader(user_id):
        extra.append(InlineKeyboardButton(text="👔 Лидерка", callback_data="m_leader"))
    if is_fsb(user_id):
        extra.append(InlineKeyboardButton(text="🕶 ФСБ", callback_data="m_fsb"))
    if extra:
        rows.append(extra)

    staff: list[InlineKeyboardButton] = []
    if is_media(user_id):
        staff.append(InlineKeyboardButton(text="🎬 Медиа", callback_data="m_media"))
    if is_admin(user_id, 1):
        staff.append(InlineKeyboardButton(text="🛠 Админка", callback_data="m_admin"))
    if staff:
        rows.append(staff)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_help_text(user_id: int | None) -> str:
    arank = get_admin_rank(user_id)
    lines = [
        "🛠 **Панель администрации CRMP**",
        f"Ваш ранг: **{ADMIN_RANKS.get(arank, str(arank))}** | Игроков в базе: `{len(users)}`\n",
        "**Все команды администрации:**",
        "• `/admin` — список команд админки (1+ ранг)",
        "• `/playerinfo <ID>` — полное досье игрока (1+ ранг)",
        "• `/clearwanted <ID>` — снять розыск игроку (1+ ранг)",
        "• `/setwanted <ID> <0..5>` — задать уровень розыска (2+ ранг)",
        "• `/givemoney <ID> <сумма>` — выдать/снять рубли (2+ ранг)",
        "• `/setlvl <ID> <уровень>` — поставить уровень (2+ ранг)",
        "• `/announce <текст>` — объявление всем игрокам (3+ ранг / медиа)",
        "• `/mediaprize <ID> <сумма>` — выдать медиа-приз (3+ ранг / медиа)",
        "• `/ban <ID> [причина]` — забанить игрока (3+ ранг)",
        "• `/unban <ID>` — разбанить игрока (3+ ранг)",
        "• `/wipe <ID>` — обнулить аккаунт игрока (4+ ранг)",
    ]
    if is_owner(user_id):
        fac_keys = ", ".join(f"`{k}`" for k in FACTIONS if k != "none")
        lines.extend(
            [
                "\n👑 **Команды создателя (5 ранг):**",
                "• `/setadmin <ID> <0..5>` — выдать/изменить/снять ранг админа",
                "• `/setmedia <ID> <0|1>` — выдать/снять медиа-админку",
                f"• `/setleader <ID> <фракция|none>` — назначить/снять лидера\nФракции: {fac_keys}",
            ]
        )
    return "\n".join(lines)


def leader_panel_text(p: dict) -> str:
    fid = p.get("faction", "none")
    fac = FACTIONS.get(fid, FACTIONS["none"])
    return (
        f"👔 **Панель лидера — {fac['name']}**\n"
        "Заявки на вступление приходят вам в личку с кнопками принятия/отклонения.\n\n"
        "• `/r <текст>` — фракционная рация\n"
        "• `/invite <ID>` — принять игрока во фракцию (1 ранг)\n"
        "• `/uninvite <ID>` — уволить игрока из фракции\n"
        "• `/setrank <ID> <1..9>` — выдать ранг сотруднику\n"
        "• `/giveprem <ID> <сумма>` — выдать премию из бюджета/системы"
    )


def fsb_panel_text(p: dict) -> str:
    mask = DISGUISES.get(p.get("disguise", "off"), "Без маскировки")
    return (
        f"🕶 **Спецслужбы ФСБ РФ**\n"
        f"Текущая маскировка: **{mask}**\n\n"
        "• `/r <текст>` — рация фракции\n"
        "• `/mask <civil|opg|dps|off>` — сменить маскировку\n"
        "• `/fsb_scan <ID>` — пробить досье игрока\n"
        "• `/fsb_raid <ID>` — провести рейд по игроку с розыском"
    )


def media_panel_text() -> str:
    return (
        "🎬 **Панель медиа-партнёра**\n"
        "• `/announce <текст>` — медиа-объявление всем игрокам\n"
        "• `/mediaprize <ID> <сумма>` — выдать приз зрителю/участнику (1..15000 ₽)"
    )


async def check_not_banned(p: dict, message: Message) -> bool:
    if is_banned(p):
        reason = p.get("ban_reason") or "причина не указана"
        await message.answer(f"🚫 Ваш аккаунт заблокирован.\nПричина: **{reason}**", parse_mode="Markdown")
        return False
    return True


async def check_cb_not_banned(p: dict, callback: CallbackQuery) -> bool:
    if is_banned(p):
        reason = p.get("ban_reason") or "причина не указана"
        await callback.answer(f"🚫 Аккаунт забанен. Причина: {reason}", show_alert=True)
        return False
    return True


dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return
    await message.answer(
        f"🇷🇺 **Добро пожаловать в CRMP Russia!**\n"
        f"Ваш игровой ID: **`{p['game_id']}`** | Город: **{CITIES[p['city']]}**\n\n"
        f"Используйте меню ниже или команды для игры.",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    uid = message.from_user.id
    sender = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(sender, message):
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/pay <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("ID и сумма должны быть целыми числами.")
        return
    if amount <= 0:
        await message.answer("Сумма перевода должна быть больше 0.")
        return
    if sender["money"] < amount:
        await message.answer("Недостаточно средств на руках.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return
    if target["tg_id"] == uid:
        await message.answer("Нельзя перевести деньги самому себе.")
        return

    sender["money"] -= amount
    target["money"] += amount
    save_state()
    await message.answer(
        f"💸 Вы перевели **{amount} ₽** игроку **{target['name']}** (`#{gid}`).",
        parse_mode="Markdown",
    )


@dp.message(Command("r"))
async def cmd_radio(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return

    fid = p.get("faction", "none")
    if fid == "none":
        await message.answer("Вы не состоите во фракции.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("Формат: `/r <сообщение>`", parse_mode="Markdown")
        return

    msg_body = html.escape(parts[1].strip())
    fac_name = html.escape(FACTIONS[fid]["name"])
    sender_name = html.escape(p["name"])
    rank_val = 10 if p.get("leader_of") == fid else int(p.get("rank", 1))
    radio_text = f"📻 <b>[{fac_name}]</b> {sender_name} (ранг {rank_val}): {msg_body}"

    sent = 0
    for k, u in users.items():
        if u.get("faction") == fid:
            try:
                target_id = int(u.get("tg_id") or k)
                await message.bot.send_message(chat_id=target_id, text=radio_text, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
    await message.answer(f"✅ Сообщение в рацию отправлено ({sent} участникам).")


# --- ЛИДЕРКА ---
@dp.message(Command("leader"))
async def cmd_leader(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return
    if not is_leader(uid):
        await message.answer("⛔ Вы не являетесь лидером фракции.")
        return
    await message.answer(leader_panel_text(p), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("invite"))
async def cmd_invite(message: Message):
    uid = message.from_user.id
    leader = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(leader, message):
        return
    if not is_leader(uid):
        await message.answer("⛔ Только лидер фракции может принимать игроков.")
        return

     parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/invite <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return

    fid = leader["faction"]
    info = FACTIONS[fid]
    if target["lvl"] < info["min_lvl"]:
        await message.answer(f"Игроку нужен минимум {info['min_lvl']} уровень.")
        return
    if info["type"] == "gos" and target["wanted"] > 0:
        await message.answer("В госструктуру нельзя принять игрока с розыском.")
        return

    target["faction"] = fid
    if target.get("leader_of") != fid:
        target["leader_of"] = None
        target["rank"] = 1
    else:
        target["rank"] = 10
    if fid != "fsb":
        target["disguise"] = "off"
    save_state()
    await message.answer(
        f"✅ Игрок **{target['name']}** (`#{gid}`) принят в **{info['name']}** (1 ранг).",
        parse_mode="Markdown",
    )


@dp.message(Command("uninvite"))
async def cmd_uninvite(message: Message):
    uid = message.from_user.id
    leader = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(leader, message):
        return
    if not is_leader(uid):
        await message.answer("⛔ Только лидер фракции может увольнять сотрудников.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/uninvite <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target or target.get("faction") != leader["faction"]:
        await message.answer("Игрок не состоит в вашей фракции.")
        return
    if target.get("tg_id") == uid:
        await message.answer("Нельзя уволить самого себя этой командой.")
        return

    target["faction"] = "none"
    target["rank"] = 1
    target["leader_of"] = None
    target["disguise"] = "off"
    save_state()
    await message.answer(f"📤 Игрок **{target['name']}** (`#{gid}`) уволен из фракции.", parse_mode="Markdown")


@dp.message(Command("setrank"))
async def cmd_setrank(message: Message):
    uid = message.from_user.id
    leader = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(leader, message):
        return
    if not is_leader(uid):
        await message.answer("⛔ Только лидер фракции может менять ранги.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setrank <игровой_ID> <1..9>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        new_rank = int(parts[2])
    except ValueError:
        await message.answer("ID и ранг должны быть числами.")
        return
    if not (1 <= new_rank <= 9):
        await message.answer("Ранг сотрудника должен быть от 1 до 9.")
        return

    target = find_by_game_id(gid)
    if not target or target.get("faction") != leader["faction"]:
        await message.answer("Игрок не состоит в вашей фракции.")
        return
    if target.get("tg_id") == uid:
        await message.answer("Лидеру нельзя менять ранг этой командой.")
        return

    target["rank"] = new_rank
    save_state()
    await message.answer(
        f"🎖 Игроку **{target['name']}** (`#{gid}`) установлен **{new_rank} ранг**.",
        parse_mode="Markdown",
    )


@dp.message(Command("giveprem"))
async def cmd_giveprem(message: Message):
    uid = message.from_user.id
    leader = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(leader, message):
        return
    if not is_leader(uid):
        await message.answer("⛔ Только лидер фракции может выдавать премии.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/giveprem <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        prem = int(parts[2])
    except ValueError:
        await message.answer("ID и сумма должны быть числами.")
        return
    if not (1 <= prem <= 10000):
        await message.answer("Премия должна быть в пределах от 1 до 10 000 ₽.")
        return

    target = find_by_game_id(gid)
    if not target or target.get("faction") != leader["faction"]:
        await message.answer("Игрок не состоит в вашей фракции.")
        return

    target["money"] += prem
    save_state()
    await message.answer(
        f"💵 Сотруднику **{target['name']}** (`#{gid}`) выдана премия **+{prem} ₽**.",
        parse_mode="Markdown",
    )


# --- ФСБ ---
@dp.message(Command("fsb"))
async def cmd_fsb(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return
    if not is_fsb(uid):
        await message.answer("⛔ Доступно только сотрудникам ФСБ.")
        return
    await message.answer(fsb_panel_text(p), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("mask"))
async def cmd_mask(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return
    if not is_fsb(uid):
        await message.answer("⛔ Маскировка доступна только сотрудникам ФСБ.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or parts[1].lower() not in DISGUISES:
        await message.answer("Формат: `/mask <civil|opg|dps|off>`", parse_mode="Markdown")
        return

    mode = parts[1].lower()
    p["disguise"] = mode
    save_state()
    await message.answer(f"🎭 Маскировка изменена: **{DISGUISES[mode]}**.", parse_mode="Markdown")


@dp.message(Command("fsb_scan"))
async def cmd_fsb_scan(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return
    if not is_fsb(uid):
        await message.answer("⛔ Доступно только сотрудникам ФСБ.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/fsb_scan <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return

    fac = FACTIONS.get(target["faction"], FACTIONS["none"])
    city = CITIES.get(target["city"], CITIES["arzamas"])
    await message.answer(
        f"🕵️‍♂️ **Оперативная справка ФСБ (#{gid})**\n"
        f"Имя: **{target['name']}** | Ур.: **{target['lvl']}**\n"
        f"Фракция: **{fac['name']}** | Город: **{city}**\n"
        f"Розыск: **{target['wanted']}/5** | Наличные: **{target['money']} ₽**",
        parse_mode="Markdown",
    )


@dp.message(Command("fsb_raid"))
async def cmd_fsb_raid(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not await check_not_banned(p, message):
        return
    if not is_fsb(uid):
        await message.answer("⛔ Рейды доступны только сотрудникам ФСБ.")
        return

    now = time.time()
    rem = int(RAID_COOLDOWN - (now - p.get("last_raid", 0.0)))
    if rem > 0:
        await message.answer(f"⏳ Следующий рейд будет доступен через {rem} сек.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/fsb_raid <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    if target.get("wanted", 0) <= 0:
        await message.answer("Рейд можно провести только по игроку в розыске.")
        return

    p["last_raid"] = now
    seized = min(target["money"], random.randint(250, 700))
    target["money"] -= seized
    target["wanted"] = max(0, target["wanted"] - 1)
    p["money"] += 300
    save_state()

    await message.answer(
        f"🚨 **Рейд ФСБ успешно проведён!**\n"
        f"Изъято у **#{gid}**: **{seized} ₽**, розыск снижен на 1⭐.\n"
        f"Ваша премия за операцию: **+300 ₽**.",
        parse_mode="Markdown",
    )


# --- АДМИНКА И МЕДИА ---
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 1):
        await message.answer("⛔ Нет прав администратора.")
        return
    await message.answer(admin_help_text(uid), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("media"))
async def cmd_media(message: Message):
    uid = message.from_user.id
    if not is_media(uid):
        await message.answer("⛔ Нет прав медиа-администратора.")
        return
    await message.answer(media_panel_text(), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("playerinfo"))
async def cmd_playerinfo(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 1):
        await message.answer("⛔ Требуется 1+ ранг администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/playerinfo <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    await message.answer(format_dossier(target), parse_mode="Markdown")


@dp.message(Command("clearwanted"))
async def cmd_clearwanted(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 1):
        await message.answer("⛔ Требуется 1+ ранг администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/clearwanted <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    target["wanted"] = 0
    save_state()
    await message.answer(f"✅ Розыск игроку **{target['name']}** (`#{gid}`) снят.", parse_mode="Markdown")


@dp.message(Command("setwanted"))
async def cmd_setwanted(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await message.answer("⛔ Требуется 2+ ранг администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setwanted <игровой_ID> <0..5>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        w = int(parts[2])
    except ValueError:
        await message.answer("ID и уровень розыска должны быть числами.")
        return
    if not (0 <= w <= 5):
        await message.answer("Уровень розыска должен быть от 0 до 5.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    target["wanted"] = w
    save_state()
    await message.answer(f"⭐ Игроку **{target['name']}** (`#{gid}`) установлен розыск `{w}/5`.", parse_mode="Markdown")


@dp.message(Command("givemoney"))
async def cmd_givemoney(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await message.answer("⛔ Требуется 2+ ранг администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/givemoney <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        delta = int(parts[2])
    except ValueError:
        await message.answer("ID и сумма должны быть числами.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    target["money"] = max(0, target["money"] + delta)
    save_state()
    await message.answer(
        f"💵 Баланс игрока **{target['name']}** (`#{gid}`) изменён на `{delta:+d} ₽`. Теперь: **{target['money']} ₽**.",
        parse_mode="Markdown",
    )


@dp.message(Command("setlvl"))
async def cmd_setlvl(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await message.answer("⛔ Требуется 2+ ранг администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setlvl <игровой_ID> <уровень>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        lvl = int(parts[2])
    except ValueError:
        await message.answer("ID и уровень должны быть числами.")
        return
    if lvl < 1:
        await message.answer("Уровень не может быть меньше 1.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    target["lvl"] = lvl
    target["xp"] = 0
    save_state()
    await message.answer(f"🎚 Игроку **{target['name']}** (`#{gid}`) установлен **{lvl} уровень**.", parse_mode="Markdown")


@dp.message(Command("mediaprize"))
async def cmd_mediaprize(message: Message):
    uid = message.from_user.id
    if not (is_admin(uid, 3) or is_media(uid)):
        await message.answer("⛔ Доступно с 3 ранга администратора или медиа-ролью.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/mediaprize <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        prize = int(parts[2])
    except ValueError:
        await message.answer("ID и сумма должны быть числами.")
        return
    if not (1 <= prize <= 15000):
        await message.answer("Приз должен быть от 1 до 15 000 ₽.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    target["money"] += prize
    save_state()
    await message.answer(
        f"🎬 Игроку **{target['name']}** (`#{gid}`) выдан медиа-приз **+{prize} ₽**!",
        parse_mode="Markdown",
    )


@dp.message(Command("announce"))
async def cmd_announce(message: Message):
    uid = message.from_user.id
    if not (is_admin(uid, 3) or is_media(uid)):
        await message.answer("⛔ Доступно с 3 ранга администратора или медиа-ролью.")
        return

    raw_text = (message.text or "").split(maxsplit=1)
    if len(raw_text) < 2 or not raw_text[1].strip():
        await message.answer("Формат: `/announce <текст объявления>`", parse_mode="Markdown")
        return

    safe_body = html.escape(raw_text[1].strip())
    header = "📢 <b>ОБЪЯВЛЕНИЕ АДМИНИСТРАЦИИ</b>"
    if not is_admin(uid, 1) and is_media(uid):
        header = "🎬 <b>МЕДИА-ОБЪЯВЛЕНИЕ</b>"
    text = f"{header}\n\n{safe_body}"

    sent_ok = 0
    sent_fail = 0

    for key, user_data in users.items():
        target_tg_id = user_data.get("tg_id")
        if not target_tg_id:
            try:
                target_tg_id = int(key)
            except ValueError:
                sent_fail += 1
                continue

        try:
            await message.bot.send_message(chat_id=target_tg_id, text=text, parse_mode="HTML")
            sent_ok += 1
            await asyncio.sleep(0.05)
        except Exception:
            sent_fail += 1

    await message.answer(
        f"✅ Рассылка завершена.\n"
        f"📨 Доставлено: **{sent_ok}**\n"
        f"⚠️ Не доставлено: **{sent_fail}**",
        parse_mode="Markdown",
    )


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    uid = message.from_user.id
    actor_rank = get_admin_rank(uid)
    if actor_rank < 3:
        await message.answer("⛔ Банить игроков можно с **3 ранга** администратора.", parse_mode="Markdown")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Формат: `/ban <игровой_ID> [причина]`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    reason = parts[2].strip() if len(parts) == 3 and parts[2].strip() else "Нарушение правил сервера"
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return

    target_tg = target.get("tg_id")
    if is_owner(target_tg):
        await message.answer("⛔ Нельзя забанить создателя проекта.")
        return
    if target_tg and get_admin_rank(target_tg) >= actor_rank and not is_owner(uid):
        await message.answer("⛔ Нельзя забанить администратора равного или старшего ранга.")
        return

    target["banned"] = True
    target["ban_reason"] = reason
    save_state()
    await message.answer(
        f"🔨 Игрок {target['name']} (#{gid}) забанен.\nПричина: {reason}",
        parse_mode=None,
    )


@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 3):
        await message.answer("⛔ Разбанивать игроков можно с **3 ранга** администратора.", parse_mode="Markdown")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/unban <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return

    target["banned"] = False
    target["ban_reason"] = ""
    save_state()
    await message.answer(
        f"🔓 Игрок {target['name']} (#{gid}) разбанен.",
        parse_mode=None,
    )


@dp.message(Command("wipe"))
async def cmd_wipe(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await message.answer("⛔ Обнулять аккаунты можно с **4 ранга** администратора.", parse_mode="Markdown")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/wipe <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return

    if is_owner(target.get("tg_id")):
        await message.answer("⛔ Нельзя обнулить аккаунт создателя проекта.")
        return

    target["money"] = 1000
    target["lvl"] = 1
    target["xp"] = 0
    target["wanted"] = 0
    target["faction"] = "none"
    target["rank"] = 1
    target["leader_of"] = None
    target["disguise"] = "off"
    target["car"] = "none"
    target["house"] = "none"
    target["city"] = "arzamas"
    target["last_shift"] = 0.0
    target["last_crime"] = 0.0
    target["last_daily"] = 0.0
    target["last_raid"] = 0.0
    save_state()

    await message.answer(
        f"🧹 Аккаунт игрока {target['name']} (#{gid}) полностью обнулён до стартовых значений.",
        parse_mode=None,
    )


@dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        await message.answer("⛔ Команда доступна только создателю проекта.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setadmin <игровой_ID> <0..5>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        arank = int(parts[2])
    except ValueError:
        await message.answer("ID и ранг должны быть числами.")
        return
    if not (0 <= arank <= 5):
        await message.answer("Ранг админа должен быть от 0 до 5.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    if is_owner(target.get("tg_id")) and arank < 5:
        await message.answer("⛔ Нельзя понизить создателя проекта.")
        return

    target["admin_rank"] = arank
    save_state()
    await message.answer(
        f"🛠 Игроку **{target['name']}** (`#{gid}`) выдан статус: **{ADMIN_RANKS[arank]}**.",
        parse_mode="Markdown",
    )


@dp.message(Command("setmedia"))
async def cmd_setmedia(message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        await message.answer("⛔ Команда доступна только создателю проекта.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3 or parts[2] not in ("0", "1"):
        await message.answer("Формат: `/setmedia <игровой_ID> <0|1>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return

    enabled = parts[2] == "1"
    target["is_media"] = enabled
    save_state()
    state_label = "выдана" if enabled else "снята"
    await message.answer(
        f"🎬 Медиа-админка игроку **{target['name']}** (`#{gid}`) **{state_label}**.",
        parse_mode="Markdown",
    )


@dp.message(Command("setleader"))
async def cmd_setleader(message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        await message.answer("⛔ Команда доступна только создателю проекта.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        fac_keys = ", ".join(f"`{k}`" for k in FACTIONS if k != "none")
        await message.answer(f"Формат: `/setleader <игровой_ID> <фракция|none>`\nДоступно: {fac_keys}", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return

    fid = parts[2].lower()
    if fid != "none" and fid not in FACTIONS:
        await message.answer("Неизвестный ключ фракции.")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return

    if fid == "none":
        target["leader_of"] = None
        if target.get("faction") != "none":
            target["rank"] = 1
        save_state()
        await message.answer(f"👔 Лидерство у игрока **{target['name']}** (`#{gid}`) снято.", parse_mode="Markdown")
        return

    target["leader_of"] = fid
    target["faction"] = fid
    target["rank"] = 10
    if fid != "fsb":
        target["disguise"] = "off"
    save_state()
    await message.answer(
        f"👑 Игрок **{target['name']}** (`#{gid}`) назначен лидером фракции **{FACTIONS[fid]['name']}** (10 ранг).",
        parse_mode="Markdown",
    )


# --- МЕНЮ И КНОПКИ ---
@dp.callback_query(F.data == "m_admin")
async def cb_admin(callback: CallbackQuery):
    uid = callback.from_user.id
    if not is_admin(uid, 1):
        await callback.answer("⛔ Нет прав администратора", show_alert=True)
        return
    await callback.message.answer(admin_help_text(uid), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_media")
async def cb_media(callback: CallbackQuery):
    uid = callback.from_user.id
    if not is_media(uid):
        await callback.answer("⛔ Нет прав медиа-администратора", show_alert=True)
        return
    await callback.message.answer(media_panel_text(), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_leader")
async def cb_leader(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    if not is_leader(uid):
        await callback.answer("⛔ Вы не лидер фракции", show_alert=True)
        return
    await callback.message.answer(leader_panel_text(p), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_fsb")
async def cb_fsb(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    if not is_fsb(uid):
        await callback.answer("⛔ Доступно только сотрудникам ФСБ", show_alert=True)
        return
    await callback.message.answer(fsb_panel_text(p), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_passport")
async def cb_passport(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    await callback.message.answer(format_passport(p), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_cities")
async def cb_cities(callback: CallbackQuery):
    p = get_player(callback.from_user.id, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, callback_data=f"go_city:{cid}")]
            for cid, title in CITIES.items()
        ]
        + [[InlineKeyboardButton(text="⬅️ В меню", callback_data="m_passport")]]
    )
    await callback.message.answer("🗺 **Навигатор по области — выбери город:**", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("go_city:"))
async def cb_go_city(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    cid = callback.data.split(":", 1)[1]
    if cid not in CITIES:
        await callback.answer("Город не найден", show_alert=True)
        return
    p["city"] = cid
    save_state()
    await callback.message.answer(
        f"🚕 Ты прибыл в **{CITIES[cid]}**!",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data == "m_work")
async def cb_work(callback: CallbackQuery):
    p = get_player(callback.from_user.id, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    rows = [[InlineKeyboardButton(text="💵 Отработать смену", callback_data="do_shift")]]
    for fid, info in FACTIONS.items():
        if fid == "none":
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📨 Заявка: {info['name']} (от {info['min_lvl']} ур.)",
                    callback_data=f"join_fac:{fid}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="m_passport")])
    await callback.message.answer(
        f"💼 **Биржа труда и фракции**\n"
        f"Текущая организация: **{FACTIONS[p['faction']]['name']}**\n"
        f"Вступление в организации осуществляется по заявкам.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown",
    )
    await callback.answer()


def _find_faction_reviewers(fid: str) -> list[int]:
    reviewers: list[int] = []
    for k, u in users.items():
        try:
            tg_id = int(u.get("tg_id") or k)
        except (ValueError, TypeError):
            continue
        if u.get("leader_of") == fid or get_admin_rank(tg_id) >= 4:
            if tg_id not in reviewers:
                reviewers.append(tg_id)
    if OWNER_ID and OWNER_ID not in reviewers:
        reviewers.append(OWNER_ID)
    return reviewers


@dp.callback_query(F.data.startswith("join_fac:"))
async def cb_join_fac(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return

    fid = callback.data.split(":", 1)[1]
    info = FACTIONS.get(fid)
    if not info or fid == "none":
        await callback.answer("Организация не найдена", show_alert=True)
        return
    if p["faction"] == fid:
        await callback.answer("Вы уже состоите в этой организации!", show_alert=True)
        return
    if p["lvl"] < info["min_lvl"]:
        await callback.answer(f"Нужен {info['min_lvl']} уровень!", show_alert=True)
        return
    if info["type"] == "gos" and p["wanted"] > 0:
        await callback.answer("В госструктуры с розыском не принимают!", show_alert=True)
        return

    for app in faction_apps.values():
        if app.get("applicant_uid") == uid and app.get("faction") == fid and app.get("status") == "pending":
            await callback.answer("⏳ Ваша заявка в эту фракцию уже на рассмотрении!", show_alert=True)
            return

    app_id = f"{uid}_{fid}_{int(time.time())}"
    faction_apps[app_id] = {
        "id": app_id,
        "applicant_uid": uid,
        "game_id": p["game_id"],
        "name": p["name"],
        "lvl": p["lvl"],
        "faction": fid,
        "status": "pending",
        "created_at": time.time(),
    }
    save_state()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"fac_app:ok:{app_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"fac_app:no:{app_id}"),
            ]
        ]
    )
    app_text = (
        f"📩 **Новая заявка во фракцию**\n"
        f"🏛 Организация: **{info['name']}**\n"
        f"👤 Игрок: **{p['name']}** (`#{p['game_id']}`)\n"
        f"🎖 Уровень: **{p['lvl']}** | ⭐ Розыск: **{p['wanted']}/5**"
    )

    notified = 0
    for r_id in _find_faction_reviewers(fid):
        try:
            await callback.bot.send_message(chat_id=r_id, text=app_text, reply_markup=kb, parse_mode="Markdown")
            notified += 1
        except Exception:
            pass

    hint = "Заявка отправлена руководству фракции." if notified else "Заявка сохранена, ожидайте рассмотрения."
    await callback.message.answer(
        f"📨 Заявка в **{info['name']}** подана!\n{hint}",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("fac_app:"))
async def cb_fac_app_decision(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Некорректные данные заявки", show_alert=True)
        return

    _, decision, app_id = parts
    app = faction_apps.get(app_id)
    if not app:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if app.get("status") != "pending":
        await callback.answer("Эта заявка уже рассмотрена", show_alert=True)
        return

    actor_id = callback.from_user.id
    fid = app["faction"]
    actor_player = users.get(str(actor_id), {})
    is_fac_leader = actor_player.get("leader_of") == fid
    if not (is_fac_leader or is_admin(actor_id, 4)):
        await callback.answer("⛔ Рассматривать заявки может лидер фракции или админ 4+ ранга", show_alert=True)
        return

    applicant_uid = int(app["applicant_uid"])
    target = users.get(str(applicant_uid))
    if not target:
        app["status"] = "closed"
        save_state()
        await callback.answer("Игрок не найден в базе", show_alert=True)
        return

    normalize_player(target, applicant_uid)
    info = FACTIONS.get(fid, FACTIONS["none"])

    if decision == "ok":
        app["status"] = "approved"
        target["faction"] = fid
        if target.get("leader_of") == fid:
            target["rank"] = 10
        else:
            if target.get("leader_of") and target["leader_of"] != fid:
                target["leader_of"] = None
            target["rank"] = 1
        if fid != "fsb":
            target["disguise"] = "off"
        save_state()

        try:
            await callback.bot.send_message(
                chat_id=applicant_uid,
                text=f"✅ Ваша заявка в **{info['name']}** одобрена! Вы приняты на **1 ранг**.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await callback.message.edit_text(
            f"✅ Заявка игрока **{target['name']}** (`#{target['game_id']}`) в **{info['name']}** **одобрена** (выдан 1 ранг).",
            parse_mode="Markdown",
        )
        await callback.answer("Игрок принят во фракцию")

    elif decision == "no":
        app["status"] = "rejected"
        save_state()

        try:
            await callback.bot.send_message(
                chat_id=applicant_uid,
                text=f"❌ Ваша заявка в **{info['name']}** отклонена.",
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await callback.message.edit_text(
            f"❌ Заявка игрока **{target['name']}** (`#{target['game_id']}`) в **{info['name']}** **отклонена**.",
            parse_mode="Markdown",
        )
        await callback.answer("Заявка отклонена")


@dp.callback_query(F.data == "do_shift")
async def cb_do_shift(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return

    now = time.time()
    rem = int(SHIFT_COOLDOWN - (now - p["last_shift"]))
    if rem > 0:
        await callback.answer(f"⏳ До следующей смены осталось {rem} сек.", show_alert=True)
        return

    fac = FACTIONS.get(p["faction"], FACTIONS["none"])
    house_bonus = HOUSES.get(p["house"], HOUSES["none"])["pay_bonus"]
    leader_bonus = 150 if p.get("leader_of") == p["faction"] and p["faction"] != "none" else 0
    rank_bonus = p["rank"] * 20 if p["faction"] != "none" else 0
    pay = random.randint(*fac["pay"]) + house_bonus + leader_bonus + rank_bonus
    xp_gain = random.randint(25, 45)

    p["last_shift"] = now
    p["money"] += pay
    lvl_up = add_xp(p, xp_gain)
    save_state()

    extra = f"\n🎉 **Новый уровень: {p['lvl']}!**" if lvl_up else ""
    await callback.message.answer(
        f"💼 Смена завершена (**{fac['name']}**)\n"
        f"💵 Зарплата: **+{pay} ₽**\n"
        f"✨ Опыт: **+{xp_gain} XP**{extra}",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data == "m_crime")
async def cb_crime(callback: CallbackQuery):
    p = get_player(callback.from_user.id, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    bribe = max(300, p["wanted"] * 400)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🦹 Пойти на дело (угон / разборки)", callback_data="do_crime")],
            [InlineKeyboardButton(text=f"🕵️ Снять розыск у решалы ({bribe} ₽)", callback_data="do_bribe")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="m_passport")],
        ]
    )
    await callback.message.answer(
        "🔫 **Криминальный мир**\n"
        "Члены ОПГ и владельцы быстрых тачек уходят от погони заметно чаще.",
        reply_markup=kb,
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data == "do_crime")
async def cb_do_crime(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return

    now = time.time()
    rem = int(CRIME_COOLDOWN - (now - p["last_crime"]))
    if rem > 0:
        await callback.answer(f"⏳ Заляг на дно ещё на {rem} сек.", show_alert=True)
        return

    p["last_crime"] = now
    car_bonus = CARS.get(p["car"], CARS["none"])["escape"]
    opg_bonus = 10 if FACTIONS.get(p["faction"], FACTIONS["none"])["type"] == "opg" else 0
    chance = min(92, 42 + car_bonus + opg_bonus)

    if random.randint(1, 100) <= chance:
        loot = random.randint(450, 950)
        xp_gain = 35
        p["money"] += loot
        lvl_up = add_xp(p, xp_gain)
        save_state()
        extra = f"\n🎉 **Новый уровень: {p['lvl']}!**" if lvl_up else ""
        await callback.message.answer(
            f"🔥 **Дело выгорело!** Ты ушёл от хвоста.\n"
            f"💰 Куш: **+{loot} ₽** | ✨ **+{xp_gain} XP**{extra}",
            reply_markup=main_kb(uid),
            parse_mode="Markdown",
        )
    else:
        fine = min(p["money"], random.randint(200, 450))
        p["money"] -= fine
        p["wanted"] = min(5, p["wanted"] + 1)
        save_state()
        await callback.message.answer(
            f"🚨 **План «Перехват»!** Патруль засёк тачку.\n"
            f"💸 Потери: **-{fine} ₽**\n"
            f"⭐ Уровень розыска: **{p['wanted']}/5**",
            reply_markup=main_kb(uid),
            parse_mode="Markdown",
        )
    await callback.answer()


@dp.callback_query(F.data == "do_bribe")
async def cb_bribe(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    if p["wanted"] == 0:
        await callback.answer("У тебя нет розыска.", show_alert=True)
        return
    cost = p["wanted"] * 400
    if p["money"] < cost:
        await callback.answer(f"Не хватает денег! Нужно {cost} ₽", show_alert=True)
        return
    p["money"] -= cost
    p["wanted"] = 0
    save_state()
    await callback.message.answer(
        f"🕵️ Решала закрыл вопрос за **{cost} ₽**. Розыск снят!",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data == "m_cars")
async def cb_cars(callback: CallbackQuery):
    p = get_player(callback.from_user.id, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    rows = []
    for cid, info in CARS.items():
        if cid == "none":
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{info['name']} — {info['price']} ₽ (+{info['escape']}% уход)",
                    callback_data=f"buy_car:{cid}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="m_passport")])
    await callback.message.answer("🚗 **Автосалон области:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_car:"))
async def cb_buy_car(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    cid = callback.data.split(":", 1)[1]
    info = CARS.get(cid)
    if not info:
        await callback.answer("Машина не найдена", show_alert=True)
        return
    if p["car"] == cid:
        await callback.answer("Эта машина уже у тебя!", show_alert=True)
        return
    if p["money"] < info["price"]:
        await callback.answer(f"Нужно {info['price']} ₽!", show_alert=True)
        return
    p["money"] -= info["price"]
    p["car"] = cid
    save_state()
    await callback.message.answer(f"🎉 Ты купил **{info['name']}**!", reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_houses")
async def cb_houses(callback: CallbackQuery):
    p = get_player(callback.from_user.id, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    rows = []
    for hid, info in HOUSES.items():
        if hid == "none":
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{info['name']} — {info['price']} ₽ (+{info['pay_bonus']} ₽ к смене)",
                    callback_data=f"buy_house:{hid}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="m_passport")])
    await callback.message.answer("🏠 **Агентство недвижимости:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_house:"))
async def cb_buy_house(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    hid = callback.data.split(":", 1)[1]
    info = HOUSES.get(hid)
    if not info:
        await callback.answer("Жильё не найдено", show_alert=True)
        return
    if p["house"] == hid:
        await callback.answer("Это жильё уже твоё!", show_alert=True)
        return
    if p["money"] < info["price"]:
        await callback.answer(f"Нужно {info['price']} ₽!", show_alert=True)
        return
    p["money"] -= info["price"]
    p["house"] = hid
    save_state()
    await callback.message.answer(f"🔑 Поздравляем с новосельем: **{info['name']}**!", reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_daily")
async def cb_daily(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return

    now = time.time()
    rem = int(DAILY_COOLDOWN - (now - p["last_daily"]))
    if rem > 0:
        hours = rem // 3600
        mins = (rem % 3600) // 60
        await callback.answer(f"⏳ Бонус будет доступен через {hours} ч. {mins} мин.", show_alert=True)
        return
    bonus = 500 + p["lvl"] * 100
    p["last_daily"] = now
    p["money"] += bonus
    save_state()
    await callback.message.answer(
        f"🎁 Ты забрал ежедневный бонус: **+{bonus} ₽**!",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data == "m_top")
async def cb_top(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not await check_cb_not_banned(p, callback):
        return
    if not users:
        await callback.answer("Список пуст", show_alert=True)
        return
    ranked = sorted(users.values(), key=lambda x: (x.get("lvl", 1), x.get("money", 0)), reverse=True)[:10]
    lines = ["🏆 **Топ-10 граждан области:**\n"]
    for idx, u in enumerate(ranked, start=1):
        lines.append(f"{idx}. **{u['name']}** (`#{u['game_id']}`) — {u['lvl']} ур. | {u['money']} ₽")
    await callback.message.answer("\n".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения!")
    load_state()
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
