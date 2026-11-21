import asyncio
import html
import json
import logging
import os
import random
import time
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = 5516435343

DATA_FILE = "crmp_russia_data.json"
START_GAME_ID = 1001

SHIFT_COOLDOWN = 45       # сек между рабочими сменами
CRIME_COOLDOWN = 60       # сек между криминальными делами
DAILY_COOLDOWN = 86400    # ежедневный бонус (24 часа)

CITIES = {
    "arzamas": "🏙 г. Арзамас",
    "yuzhny": "🌊 г. Южный",
    "batyrevo": "🏘 пгт. Батырево",
    "lytkarino": "🏭 г. Лыткарино",
    "edovo": "🌲 с. Эдово",
}

FACTIONS = {
    "none": {"name": "Гражданский", "pay": (60, 120), "min_lvl": 1, "type": "civil"},
    "courier": {"name": "📦 Яндекс.Доставка", "pay": (140, 230), "min_lvl": 1, "type": "civil"},
    "trucker": {"name": "🚛 Дальнобойщик", "pay": (280, 420), "min_lvl": 2, "type": "civil"},
    "mechanic": {"name": "🔧 Автомеханик СТО", "pay": (230, 360), "min_lvl": 2, "type": "civil"},
    "dps": {"name": "🚓 УГИБДД (ДПС)", "pay": (380, 560), "min_lvl": 3, "type": "gos"},
    "pps": {"name": "👮 УМВД (ППС)", "pay": (360, 540), "min_lvl": 3, "type": "gos"},
    "mchs": {"name": "🚒 МЧС России", "pay": (350, 520), "min_lvl": 3, "type": "gos"},
    "fsb": {"name": "🛡 ФСБ России", "pay": (460, 680), "min_lvl": 5, "type": "gos"},
    "opg_sun": {"name": "🔫 ОПГ «Солнцевские»", "pay": (320, 500), "min_lvl": 2, "type": "opg"},
    "opg_orekh": {"name": "🔪 ОПГ «Ореховские»", "pay": (320, 500), "min_lvl": 2, "type": "opg"},
}

CARS = {
    "none": {"name": "Пешком", "price": 0, "escape": 0},
    "vaz2107": {"name": "🚗 ВАЗ-2107 «Семёрка»", "price": 1200, "escape": 6},
    "priora": {"name": "🚘 Lada Priora (БПАН)", "price": 3500, "escape": 14},
    "camry": {"name": "🚙 Toyota Camry 3.5", "price": 10000, "escape": 24},
    "bmw_m5": {"name": "🏎 BMW M5 F90", "price": 28000, "escape": 36},
    "gelik": {"name": "🖤 Mercedes-AMG G63", "price": 60000, "escape": 48},
}

HOUSES = {
    "none": {"name": "Без прописки (вокзал)", "price": 0, "pay_bonus": 0},
    "obshaga": {"name": "🚪 Комната в общаге", "price": 2500, "pay_bonus": 30},
    "khrush": {"name": "🏢 Двушка в хрущёвке", "price": 9000, "pay_bonus": 80},
    "cottage": {"name": "🏰 Коттедж на Рублёвке", "price": 45000, "pay_bonus": 220},
}


def load_state() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"next_id": START_GAME_ID, "users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict) and "users" in raw:
                return raw
    except Exception:
        pass
    return {"next_id": START_GAME_ID, "users": {}}


def save_state() -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


state: dict = load_state()
users: dict[str, dict] = state["users"]


def normalize_player(p: dict, tg_id: int, full_name: str = "") -> dict:
    p["tg_id"] = tg_id
    if full_name:
        p["name"] = full_name
    p.setdefault("money", 1000)
    p.setdefault("lvl", 1)
    p.setdefault("xp", 0)
    p.setdefault("wanted", 0)
    p.setdefault("faction", "none")
    if p["faction"] not in FACTIONS:
        p["faction"] = "none"
    p.setdefault("rank", 1)
    p.setdefault("leader_of", None)
    if p["leader_of"] not in FACTIONS or p["leader_of"] == "none":
        p["leader_of"] = None
    p.setdefault("is_admin", False)
    p.setdefault("is_media", False)
    p.setdefault("car", "none")
    p.setdefault("house", "none")
    p.setdefault("city", "arzamas")
    p.setdefault("last_shift", 0.0)
    p.setdefault("last_crime", 0.0)
    p.setdefault("last_daily", 0.0)
    return p


def get_player(tg_id: int, full_name: str = "") -> dict:
    key = str(tg_id)
    if key not in users:
        gid = int(state.get("next_id", START_GAME_ID))
        state["next_id"] = gid + 1
        users[key] = normalize_player(
            {
                "tg_id": tg_id,
                "game_id": gid,
                "name": full_name or f"Гражданин_{gid}",
            },
            tg_id,
            full_name,
        )
        save_state()
    else:
        normalize_player(users[key], tg_id, full_name)
    return users[key]


def find_by_game_id(game_id: int) -> dict | None:
    for key, u in users.items():
        try:
            tg_id = int(u.get("tg_id") or key)
        except ValueError:
            tg_id = 0
        normalize_player(u, tg_id)
        if u.get("game_id") == game_id:
            return u
    return None


def add_xp(p: dict, amount: int) -> bool:
    p["xp"] += amount
    up = False
    while p["xp"] >= p["lvl"] * 120:
        p["xp"] -= p["lvl"] * 120
        p["lvl"] += 1
        p["rank"] = min(10, p["lvl"])
        up = True
    return up


def is_owner(user_id: int | None) -> bool:
    return user_id == OWNER_ID


def is_admin(user_id: int | None) -> bool:
    if is_owner(user_id):
        return True
    if not user_id:
        return False
    u = users.get(str(user_id))
    return bool(u and u.get("is_admin"))


def is_media(user_id: int | None) -> bool:
    if is_admin(user_id):
        return True
    if not user_id:
        return False
    u = users.get(str(user_id))
    return bool(u and u.get("is_media"))


def is_leader(user_id: int | None) -> bool:
    if not user_id:
        return False
    u = users.get(str(user_id))
    return bool(u and u.get("leader_of"))


def get_roles_badges(p: dict) -> list[str]:
    badges = []
    uid = p.get("tg_id")
    if is_owner(uid):
        badges.append("👑 Создатель")
    elif p.get("is_admin"):
        badges.append("🛡 Администратор")
    if p.get("is_media"):
        badges.append("🎬 Медиа-админ")
    if p.get("leader_of") in FACTIONS and p.get("leader_of") != "none":
        fac_name = FACTIONS[p["leader_of"]]["name"]
        badges.append(f"💼 Лидер ({fac_name})")
    return badges


def main_kb(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🪪 Паспорт", callback_data="m_passport"),
            InlineKeyboardButton(text="🗺 Навигатор", callback_data="m_cities"),
        ],
        [
            InlineKeyboardButton(text="💼 Работа / Фракции", callback_data="m_work"),
            InlineKeyboardButton(text="🔫 Криминал / ОПГ", callback_data="m_crime"),
        ],
        [
            InlineKeyboardButton(text="🚗 Автосалон", callback_data="m_cars"),
            InlineKeyboardButton(text="🏠 Недвижимость", callback_data="m_houses"),
        ],
        [
            InlineKeyboardButton(text="🎁 Ежедневный бонус", callback_data="m_daily"),
            InlineKeyboardButton(text="🏆 Топ области", callback_data="m_top"),
        ],
    ]
    extra_row = []
    if is_leader(user_id):
        extra_row.append(InlineKeyboardButton(text="👔 Лидерка", callback_data="m_leader"))
    if is_media(user_id) and not is_admin(user_id):
        extra_row.append(InlineKeyboardButton(text="🎬 Медиа", callback_data="m_media"))
    if is_admin(user_id):
        extra_row.append(InlineKeyboardButton(text="🛠 Админка", callback_data="m_admin"))
    if extra_row:
        rows.append(extra_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_passport(p: dict) -> str:
    fac = FACTIONS.get(p["faction"], FACTIONS["none"])
    car = CARS.get(p["car"], CARS["none"])
    house = HOUSES.get(p["house"], HOUSES["none"])
    city = CITIES.get(p["city"], CITIES["arzamas"])
    stars = "⭐" * p["wanted"] if p["wanted"] > 0 else "Чист"
    need_xp = p["lvl"] * 120
    badges = get_roles_badges(p)
    role_line = f"🎖 Должности: **{', '.join(badges)}**\n" if badges else ""
    return (
        f"🪪 **Паспорт гражданина РФ**\n"
        f"{role_line}"
        f"👤 Имя: **{p['name']}** | 🆔 Игровой ID: **`{p['game_id']}`**\n\n"
        f"💵 Наличные: **{p['money']} ₽**\n"
        f"🎖 Уровень: **{p['lvl']}** (`{p['xp']}/{need_xp} XP`)\n"
        f"🏛 Организация: **{fac['name']}** (Ранг: `{p['rank']}/10`)\n"
        f"🚘 Транспорт: **{car['name']}**\n"
        f"🏠 Прописка: **{house['name']}**\n"
        f"📍 Город: **{city}**\n"
        f"🚨 Розыск: **{stars}**"
    )


def leader_panel_text(p: dict) -> str:
    fac_id = p.get("leader_of")
    fac = FACTIONS.get(fac_id or "none", FACTIONS["none"])
    members = [u for u in users.values() if u.get("faction") == fac_id]
    return (
        f"👔 **Панель лидера фракции**\n"
        f"🏛 Организация: **{fac['name']}**\n"
        f"👥 Состав в организации: **{len(members)} чел.**\n"
        f"💵 Бонус лидера к смене: **+150 ₽**\n\n"
        f"`/giveprem <игровой_ID> <сумма>` — выдать премию игроку (до 5 000 ₽)"
    )


def media_panel_text() -> str:
    return (
        "🎬 **Панель медиа-администратора**\n\n"
        "`/announce <текст>` — объявление игрокам\n"
        "`/mediaprize <игровой_ID> <сумма>` — выдать приз за конкурс/ролик (до 15 000 ₽)"
    )


def admin_help_text(user_id: int | None) -> str:
    lines = [
        "🛠 **Панель администрации CRMP**",
        f"Игроков в базе: `{len(users)}`\n",
        "`/givemoney <ID> <сумма>` — выдать/снять рубли",
        "`/setlvl <ID> <уровень>` — поставить уровень",
        "`/clearwanted <ID>` — снять розыск игроку",
        "`/announce <текст>` — объявление всем игрокам",
        "`/mediaprize <ID> <сумма>` — выдать медиа-приз",
    ]
    if is_owner(user_id):
        fac_keys = ", ".join(f"`{k}`" for k in FACTIONS if k != "none")
        lines.extend(
            [
                "\n👑 **Команды владельца:**",
                "`/setadmin <ID> <0|1>` — выдать/снять админку",
                "`/setmedia <ID> <0|1>` — выдать/снять медиа-админку",
                f"`/setleader <ID> <фракция|none>` — назначить/снять лидера\nФракции: {fac_keys}",
            ]
        )
    return "\n".join(lines)


dp = Dispatcher()


@dp.message(CommandStart())
@dp.message(Command("menu"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await message.answer(
        "🇷🇺 **CRMP — Криминальная Россия**\n"
        "Перевод игроку по ID: `/pay 1001 500`\n\n"
        + format_passport(p),
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    uid = message.from_user.id
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/pay <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        target_gid = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("Игровой ID и сумма должны быть числами.")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0.")
        return

    sender = get_player(uid, message.from_user.full_name)
    if sender["game_id"] == target_gid:
        await message.answer("Нельзя перевести деньги самому себе.")
        return

    target = find_by_game_id(target_gid)
    if not target:
        await message.answer(f"Игрок с ID `{target_gid}` не найден.", parse_mode="Markdown")
        return

    if sender["money"] < amount:
        await message.answer(f"Недостаточно средств! На руках: **{sender['money']} ₽**", parse_mode="Markdown")
        return

    sender["money"] -= amount
    target["money"] += amount
    save_state()
    await message.answer(
        f"💸 Переведено **{amount} ₽** игроку **{target['name']}** (ID `{target_gid}`).",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


# --- КОМАНДЫ ЛИДЕРА ---
@dp.message(Command("leader"))
async def cmd_leader_panel(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not is_leader(uid):
        await message.answer("⛔ Вы не являетесь лидером ни одной фракции.")
        return
    await message.answer(leader_panel_text(p), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("giveprem"))
async def cmd_giveprem(message: Message):
    uid = message.from_user.id
    leader = get_player(uid, message.from_user.full_name)
    if not is_leader(uid):
        await message.answer("⛔ Команда доступна только лидерам фракций.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/giveprem <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Нужны целые числа.")
        return

    if amount <= 0 or amount > 5000:
        await message.answer("Сумма премии должна быть от `1` до `5000` ₽.", parse_mode="Markdown")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return

    target["money"] += amount
    save_state()
    await message.answer(
        f"💼 Лидер **{leader['name']}** выдал премию **{amount} ₽** игроку **{target['name']}** (`#{gid}`).",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


# --- КОМАНДЫ МЕДИА-АДМИНА ---
@dp.message(Command("media"))
async def cmd_media_panel(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    if not is_media(uid):
        await message.answer("⛔ Нет прав медиа-администратора.")
        return
    await message.answer(media_panel_text(), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("mediaprize"))
async def cmd_mediaprize(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    if not is_media(uid):
        await message.answer("⛔ Нет прав медиа-администратора.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/mediaprize <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Нужны целые числа.")
        return

    if amount <= 0 or amount > 15000:
        await message.answer("Сумма медиа-приза должна быть от `1` до `15000` ₽.", parse_mode="Markdown")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return

    target["money"] += amount
    save_state()
    await message.answer(
        f"🎬 Выдан медиа-приз **{amount} ₽** игроку **{target['name']}** (`#{gid}`).",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


# --- АДМИН-КОМАНДЫ И КОМАНДЫ ВЛАДЕЛЬЦА ---
@dp.message(Command("admin"))
async def cmd_admin_help(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    if not is_admin(uid):
        await message.answer("⛔ Нет доступа к админ-панели.")
        return
    await message.answer(admin_help_text(uid), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("givemoney"))
async def cmd_givemoney(message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.answer("⛔ Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/givemoney <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid, amount = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Нужны целые числа.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return
    target["money"] = max(0, target["money"] + amount)
    save_state()
    await message.answer(f"✅ Баланс игрока `{gid}` ({target['name']}): **{target['money']} ₽**", parse_mode="Markdown")


@dp.message(Command("setlvl"))
async def cmd_setlvl(message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.answer("⛔ Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setlvl <игровой_ID> <уровень>`", parse_mode="Markdown")
        return
    try:
        gid, lvl = int(parts[1]), max(1, int(parts[2]))
    except ValueError:
        await message.answer("Нужны целые числа.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return
    target["lvl"] = lvl
    target["rank"] = min(10, lvl)
    save_state()
    await message.answer(f"✅ Игроку `{gid}` установлен **{lvl} уровень**.", parse_mode="Markdown")


@dp.message(Command("clearwanted"))
async def cmd_admin_clearwanted(message: Message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.answer("⛔ Нет доступа.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Формат: `/clearwanted <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Нужен числовой игровой ID.")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return
    target["wanted"] = 0
    save_state()
    await message.answer(f"✅ Розыск игрока `{gid}` снят.", parse_mode="Markdown")


@dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        await message.answer("⛔ Выдавать и снимать админки может только создатель проекта.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setadmin <игровой_ID> <0|1>`", parse_mode="Markdown")
        return
    try:
        gid, flag = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Нужны целые числа.")
        return
    if flag not in (0, 1):
        await message.answer("Укажи `1` (выдать) или `0` (снять).", parse_mode="Markdown")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return
    target["is_admin"] = bool(flag)
    save_state()
    status = "выдана админка" if flag else "снята админка"
    await message.answer(f"👑 Игроку `{gid}` ({target['name']}) {status}.", parse_mode="Markdown")


@dp.message(Command("setmedia"))
async def cmd_setmedia(message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        await message.answer("⛔ Выдавать и снимать медиа-админки может только создатель проекта.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: `/setmedia <игровой_ID> <0|1>`", parse_mode="Markdown")
        return
    try:
        gid, flag = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Нужны целые числа.")
        return
    if flag not in (0, 1):
        await message.answer("Укажи `1` (выдать) или `0` (снять).", parse_mode="Markdown")
        return
    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return
    target["is_media"] = bool(flag)
    save_state()
    status = "выдана медиа-админка" if flag else "снята медиа-админка"
    await message.answer(f"🎬 Игроку `{gid}` ({target['name']}) {status}.", parse_mode="Markdown")


@dp.message(Command("setleader"))
async def cmd_setleader(message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        await message.answer("⛔ Назначать и снимать лидеров может только создатель проекта.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        fac_keys = ", ".join(f"`{k}`" for k in FACTIONS if k != "none")
        await message.answer(
            f"Формат: `/setleader <игровой_ID> <фракция|none>`\nФракции: {fac_keys}",
            parse_mode="Markdown",
        )
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await message.answer("Игровой ID должен быть числом.")
        return
    fac_id = parts[2].strip().lower()
    if fac_id != "none" and fac_id not in FACTIONS:
        fac_keys = ", ".join(f"`{k}`" for k in FACTIONS if k != "none")
        await message.answer(f"Неизвестная фракция. Доступны: {fac_keys} или `none`.", parse_mode="Markdown")
        return

    target = find_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким игровым ID не найден.")
        return

    if fac_id == "none":
        target["leader_of"] = None
        save_state()
        await message.answer(f"👔 Игрок `{gid}` ({target['name']}) снят с лидерки.", parse_mode="Markdown")
        return

    for u in users.values():
        if u.get("leader_of") == fac_id and u.get("game_id") != gid:
            u["leader_of"] = None

    target["leader_of"] = fac_id
    target["faction"] = fac_id
    target["rank"] = 10
    save_state()
    await message.answer(
        f"👔 Игрок `{gid}` ({target['name']}) назначен лидером фракции **{FACTIONS[fac_id]['name']}**!",
        parse_mode="Markdown",
    )


@dp.message(Command("announce"))
async def cmd_announce(message: Message, bot: Bot):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    if not is_media(uid):
        await message.answer("⛔ Нет доступа.")
        return

    raw_text = (message.text or "").split(maxsplit=1)
    if len(raw_text) < 2 or not raw_text[1].strip():
        await message.answer("Формат: `/announce <текст объявления>`", parse_mode="Markdown")
        return

    safe_body = html.escape(raw_text[1].strip())
    header = "📢 <b>ОБЪЯВЛЕНИЕ АДМИНИСТРАЦИИ</b>"
    if not is_admin(uid) and is_media(uid):
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
            await bot.send_message(chat_id=target_tg_id, text=text, parse_mode="HTML")
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


# --- МЕНЮ И КНОПКИ ---
@dp.callback_query(F.data == "m_admin")
async def cb_admin(callback: CallbackQuery):
    uid = callback.from_user.id
    if not is_admin(uid):
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
    if not is_leader(uid):
        await callback.answer("⛔ Вы не лидер фракции", show_alert=True)
        return
    await callback.message.answer(leader_panel_text(p), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_passport")
async def cb_passport(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    await callback.message.answer(format_passport(p), reply_markup=main_kb(uid), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "m_cities")
async def cb_cities(callback: CallbackQuery):
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
    cid = callback.data.split(":", 1)[1]
    if cid not in CITIES:
        await callback.answer("Город не найден", show_alert=True)
        return
    p = get_player(uid, callback.from_user.full_name)
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
    rows = [[InlineKeyboardButton(text="💵 Отработать смену", callback_data="do_shift")]]
    for fid, info in FACTIONS.items():
        if fid == "none":
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{info['name']} (от {info['min_lvl']} ур.)",
                    callback_data=f"join_fac:{fid}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data="m_passport")])
    await callback.message.answer(
        f"💼 **Биржа труда и фракции**\nТекущая организация: **{FACTIONS[p['faction']]['name']}**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("join_fac:"))
async def cb_join_fac(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    info = FACTIONS.get(fid)
    if not info:
        await callback.answer("Организация не найдена", show_alert=True)
        return
    p = get_player(uid, callback.from_user.full_name)
    if p["lvl"] < info["min_lvl"]:
        await callback.answer(f"Нужен {info['min_lvl']} уровень!", show_alert=True)
        return
    if info["type"] == "gos" and p["wanted"] > 0:
        await callback.answer("В госструктуры с розыском не принимают!", show_alert=True)
        return
    p["faction"] = fid
    if p.get("leader_of") and p["leader_of"] != fid:
        p["leader_of"] = None
    save_state()
    await callback.message.answer(
        f"✅ Ты вступил в **{info['name']}**!",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.callback_query(F.data == "do_shift")
async def cb_do_shift(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    now = time.time()
    rem = int(SHIFT_COOLDOWN - (now - p["last_shift"]))
    if rem > 0:
        await callback.answer(f"⏳ До следующей смены осталось {rem} сек.", show_alert=True)
        return

    fac = FACTIONS.get(p["faction"], FACTIONS["none"])
    house_bonus = HOUSES.get(p["house"], HOUSES["none"])["pay_bonus"]
    leader_bonus = 150 if p.get("leader_of") == p["faction"] and p["faction"] != "none" else 0
    pay = random.randint(*fac["pay"]) + house_bonus + leader_bonus + (p["rank"] * 15)
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
    cid = callback.data.split(":", 1)[1]
    info = CARS.get(cid)
    if not info:
        await callback.answer("Машина не найдена", show_alert=True)
        return
    p = get_player(uid, callback.from_user.full_name)
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
    hid = callback.data.split(":", 1)[1]
    info = HOUSES.get(hid)
    if not info:
        await callback.answer("Жильё не найдено", show_alert=True)
        return
    p = get_player(uid, callback.from_user.full_name)
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
    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
