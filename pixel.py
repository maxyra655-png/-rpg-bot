import json
import os
import random
import time
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE")
DATA_FILE = os.getenv("DATA_FILE", "crmp_russia_data.json")
CREATOR_ID = int(os.getenv("CREATOR_ID", "5516435343"))

FACTIONS: dict[str, dict[str, Any]] = {
    "dps": {"name": "ГИБДД / ДПС", "salary": 1800, "npc": "Инспектор Воробьёв"},
    "pps": {"name": "УМВД / ППС", "salary": 1750, "npc": "Сержант Соколов"},
    "fsb": {"name": "ФСБ России", "salary": 2400, "npc": "Майор Орлов"},
    "opg_sun": {"name": "ОПГ «Солнцевские»", "salary": 2100, "npc": "Авторитет Зверь"},
}

SHOP_CARS: dict[str, dict[str, Any]] = {
    "vaz_2107": {"name": "ВАЗ-2107", "price": 120000, "bonus_work": 250},
    "priora": {"name": "LADA Priora", "price": 350000, "bonus_work": 600},
    "camry": {"name": "Toyota Camry 3.5", "price": 1450000, "bonus_work": 1400},
    "m5_f90": {"name": "BMW M5 F90", "price": 4800000, "bonus_work": 3000},
}

SHOP_HOUSES: dict[str, dict[str, Any]] = {
    "kh rushchevka": {"name": "Квартира в хрущёвке", "price": 450000, "bonus_bank": 500},
    "cottage": {"name": "Загородный коттедж", "price": 2200000, "bonus_bank": 1800},
    "villa": {"name": "Элитная вилла на Рублёвке", "price": 7500000, "bonus_bank": 5000},
}

DEFAULT_BUSINESSES: dict[str, dict[str, Any]] = {
    "24_7_center": {
        "name": "Магазин 24/7 «Центральный»",
        "price": 1200000,
        "income_per_hour": 4500,
        "owner_uid": None,
        "owner_name": None,
        "cash": 0,
        "last_collect": 0.0,
    },
    "sto_ring": {
        "name": "СТО «Кольцевая»",
        "price": 2500000,
        "income_per_hour": 9500,
        "owner_uid": None,
        "owner_name": None,
        "cash": 0,
        "last_collect": 0.0,
    },
    "club_night": {
        "name": "Ночной клуб «Москва»",
        "price": 5000000,
        "income_per_hour": 19000,
        "owner_uid": None,
        "owner_name": None,
        "cash": 0,
        "last_collect": 0.0,
    },
}

users: dict[str, dict[str, Any]] = {}
faction_apps: dict[str, dict[str, Any]] = {}
businesses: dict[str, dict[str, Any]] = {}
families: dict[str, dict[str, Any]] = {}
promocodes: dict[str, dict[str, Any]] = {}
support_tickets: dict[str, dict[str, Any]] = {}
next_game_id: int = 100
next_ticket_id: int = 1


class SupportStates(StatesGroup):
    waiting_message = State()


def normalize_player(u: dict[str, Any], tg_id: int) -> dict[str, Any]:
    global next_game_id
    u["tg_id"] = int(tg_id)
    if not u.get("game_id"):
        u["game_id"] = next_game_id
        next_game_id += 1
    else:
        u["game_id"] = int(u["game_id"])
        if u["game_id"] >= next_game_id:
            next_game_id = u["game_id"] + 1
    u["name"] = str(u.get("name") or f"Игрок_{tg_id}")
    u["lvl"] = max(1, int(u.get("lvl", 1)))
    u["xp"] = max(0, int(u.get("xp", 0)))
    u["money"] = int(u.get("money", 5000))
    u["bank"] = int(u.get("bank", 0))
    u["faction"] = str(u.get("faction") or "none")
    u["rank"] = max(1, min(10, int(u.get("rank", 1))))
    u["leader_of"] = u.get("leader_of") if u.get("leader_of") in FACTIONS else None
    u["admin_lvl"] = max(0, min(5, int(u.get("admin_lvl", 0))))
    u["helper_lvl"] = max(0, min(3, int(u.get("helper_lvl", 0))))
    u["is_media"] = bool(u.get("is_media", False))
    u["banned"] = bool(u.get("banned", False))
    u["ban_reason"] = str(u.get("ban_reason") or "")
    u["wanted"] = max(0, min(6, int(u.get("wanted", 0))))
    u["fines"] = max(0, int(u.get("fines", 0)))
    u["last_work"] = float(u.get("last_work", 0.0))
    u["last_npc"] = float(u.get("last_npc", 0.0))
    u["cars"] = list(u.get("cars") or [])
    u["houses"] = list(u.get("houses") or [])
    u["family_id"] = u.get("family_id")
    u["active_ticket"] = u.get("active_ticket")
    return u


def get_player(tg_id: int, full_name: str = "") -> dict[str, Any]:
    key = str(tg_id)
    if key not in users or not isinstance(users[key], dict):
        users[key] = normalize_player({"name": full_name or f"Игрок_{tg_id}"}, tg_id)
        save_state()
    else:
        normalize_player(users[key], tg_id)
        if full_name and users[key]["name"].startswith("Игрок_"):
            users[key]["name"] = full_name
    return users[key]


def find_player_by_game_id(game_id: int) -> dict[str, Any] | None:
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            normalize_player(u, tg_id)
            if int(u.get("game_id", 0)) == game_id:
                return u
    return None


def is_creator(uid: int) -> bool:
    return CREATOR_ID != 0 and int(uid) == CREATOR_ID


def is_admin(uid: int, min_lvl: int = 1) -> bool:
    if is_creator(uid):
        return True
    u = users.get(str(uid))
    if not isinstance(u, dict):
        return False
    return int(u.get("admin_lvl", 0)) >= min_lvl


def is_helper(uid: int, min_lvl: int = 1) -> bool:
    if is_admin(uid, 1):
        return True
    u = users.get(str(uid))
    if not isinstance(u, dict):
        return False
    return int(u.get("helper_lvl", 0)) >= min_lvl


def is_media(uid: int) -> bool:
    if is_creator(uid):
        return True
    u = users.get(str(uid))
    if not isinstance(u, dict):
        return False
    return bool(u.get("is_media", False))


def is_police_faction(u: dict[str, Any]) -> bool:
    return str(u.get("faction") or "") in {"dps", "pps", "fsb"} or is_admin(int(u.get("tg_id", 0)), 1)


def load_state() -> None:
    global next_game_id, next_ticket_id
    users.clear()
    faction_apps.clear()
    businesses.clear()
    families.clear()
    promocodes.clear()
    support_tickets.clear()

    for bid, bdef in DEFAULT_BUSINESSES.items():
        businesses[bid] = dict(bdef)

    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return

    if not isinstance(raw, dict):
        return

    next_game_id = max(100, int(raw.get("next_game_id", 100)))
    next_ticket_id = max(1, int(raw.get("next_ticket_id", 1)))

    raw_users = raw.get("users") if isinstance(raw.get("users"), dict) else {}
    for k, v in raw_users.items():
        if isinstance(v, dict):
            try:
                tg_id = int(v.get("tg_id") or k)
            except ValueError:
                continue
            users[str(tg_id)] = normalize_player(dict(v), tg_id)

    raw_apps = raw.get("faction_apps") if isinstance(raw.get("faction_apps"), dict) else {}
    for aid, aval in raw_apps.items():
        if isinstance(aval, dict):
            faction_apps[str(aid)] = dict(aval)

    raw_biz = raw.get("businesses") if isinstance(raw.get("businesses"), dict) else {}
    for bid, bval in raw_biz.items():
        if isinstance(bval, dict):
            base = dict(DEFAULT_BUSINESSES.get(bid, {
                "name": str(bval.get("name") or bid),
                "price": int(bval.get("price", 1000000)),
                "income_per_hour": int(bval.get("income_per_hour", 5000)),
                "owner_uid": None,
                "owner_name": None,
                "cash": 0,
                "last_collect": 0.0,
            }))
            base.update(bval)
            businesses[str(bid)] = base

    raw_fams = raw.get("families") if isinstance(raw.get("families"), dict) else {}
    for fid, fval in raw_fams.items():
        if isinstance(fval, dict):
            families[str(fid)] = dict(fval)

    raw_promos = raw.get("promocodes") if isinstance(raw.get("promocodes"), dict) else {}
    for code, pdata in raw_promos.items():
        if isinstance(pdata, dict):
            c_up = str(code).upper()
            promocodes[c_up] = {
                "code": c_up,
                "money": max(0, int(pdata.get("money", 0))),
                "xp": max(0, int(pdata.get("xp", 0))),
                "uses_left": max(0, int(pdata.get("uses_left", 0))),
                "used_by": [int(x) for x in pdata.get("used_by", []) if str(x).isdigit()],
            }

    raw_tickets = raw.get("support_tickets") if isinstance(raw.get("support_tickets"), dict) else {}
    for tid, tdata in raw_tickets.items():
        if isinstance(tdata, dict):
            support_tickets[str(tid)] = dict(tdata)


def save_state() -> None:
    payload = {
        "next_game_id": next_game_id,
        "next_ticket_id": next_ticket_id,
        "users": users,
        "faction_apps": faction_apps,
        "businesses": businesses,
        "families": families,
        "promocodes": promocodes,
        "support_tickets": support_tickets,
    }
    tmp_file = f"{DATA_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, DATA_FILE)


class BanMiddleware:
    async def __call__(self, handler, event, data):
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id

        if uid is not None and not is_creator(uid):
            u = users.get(str(uid))
            if isinstance(u, dict) and u.get("banned"):
                reason = u.get("ban_reason") or "Нарушение правил сервера"
                text = f"🚫 Ваш аккаунт заблокирован.\nПричина: {reason}"
                if isinstance(event, Message):
                    await event.answer(text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(text, show_alert=True)
                return
        return await handler(event, data)


def main_kb(uid: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💵 Работа")],
        [KeyboardButton(text="🏢 Бизнесы"), KeyboardButton(text="🏠 Недвижимость")],
        [KeyboardButton(text="🚗 Автосалон"), KeyboardButton(text="👨‍👩‍👧‍👦 Семья")],
        [KeyboardButton(text="🏛 Фракции"), KeyboardButton(text="🏆 Топ-10")],
        [KeyboardButton(text="🎫 Поддержка"), KeyboardButton(text="📖 Команды")],
    ]
    if is_media(uid):
        rows.append([KeyboardButton(text="🎬 Медиа")])
    if is_helper(uid, 1):
        rows.append([KeyboardButton(text="🛟 Хелперка")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)



async def safe_answer(message: Message, text: str, **kwargs) -> Message:
    try:
        return await message.answer(text, **kwargs)
    except Exception:
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "parse_mode"}
        return await message.answer(text, **clean_kwargs)


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> Message | None:
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except Exception:
        clean_kwargs = {k: v for k, v in kwargs.items() if k != "parse_mode"}
        try:
            return await bot.send_message(chat_id, text, **clean_kwargs)
        except Exception:
            return None


dp = Dispatcher()
dp.message.middleware(BanMiddleware())
dp.callback_query.middleware(BanMiddleware())


@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await safe_answer(message, 
        f"🇷🇺 Добро пожаловать в **Criminal Russia RP**!\n"
        f"Имя: **{p['name']}** | Игровой ID: **`#{p['game_id']}`**\n"
        f"Наличные: **{p['money']} ₽** | Банк: **{p['bank']} ₽** | Уровень: **{p['lvl']}**",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("help"))
@dp.message(F.text == "📖 Команды")
async def cmd_help(message: Message):
    uid = message.from_user.id
    lines = [
        "📖 **Основные команды и механики:**",
        "• `/start` — запуск и обновление меню",
        "• `/work` — отработать смену",
        "• `/promo <КОД>` — активировать промокод",
        "• `/support <текст>` — написать в поддержку (или кнопка «🎫 Поддержка»)",
        "• `/members [фракция]` — состав фракции",
        "• `/r <текст>` — рация фракции",
        "",
        "🚓 **ДПС / ППС / ФСБ:**",
        "• `/wanted <ID> <1..6>` — выдать розыск",
        "• `/clear <ID>` — снять розыск",
        "• `/fine <ID> <сумма> [причина]` — выписать штраф",
        "",
        "🛟 **Хелперы и Поддержка:**",
        "• `/tickets` — открытые обращения",
        "• `/answer <ID_тикета> <ответ>` — ответить игроку в тикете",
        "• `/closeticket <ID_тикета>` — закрыть обращение",
        "",
        "🎬 **Медиа:**",
        "• `/mediaprize <ID> <сумма>` — медиа-приз (1..15 000 ₽)",
        "• `/announce <текст>` — объявление всем игрокам",
    ]
    if is_admin(uid, 1):
        lines.extend([
            "",
            "🛡 **Администрация:**",
            "• `/players` — список игроков",
            "• `/addpromo <КОД> <сумма> <xp> <активаций>` — создать промокод",
            "• `/delpromo <КОД>` — удалить промокод",
            "• `/sethelper <ID> <0..3>` — выдать уровень хелпера",
            "• `/setmedia <ID> <0|1>` — выдать роль медиа",
            "• `/setadmin <ID> <0..5>` — выдать уровень админа",
            "• `/ban <ID> [причина]` и `/unban <ID>`",
        ])
    await safe_answer(message, "\n".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(F.text == "👤 Профиль")
async def btn_profile(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fac_key = p.get("faction", "none")
    fac_name = FACTIONS[fac_key]["name"] if fac_key in FACTIONS else "Гражданский"
    role_tag = " 👑 Лидер" if p.get("leader_of") else ""
    cars_txt = ", ".join(SHOP_CARS[c]["name"] for c in p["cars"] if c in SHOP_CARS) or "Нет"
    houses_txt = ", ".join(SHOP_HOUSES[h]["name"] for h in p["houses"] if h in SHOP_HOUSES) or "Нет"

    await safe_answer(message, 
        f"👤 **Профиль: {p['name']}** (`#{p['game_id']}`)\n"
        f"⭐ Уровень: **{p['lvl']}** (опыт: `{p['xp']}`)\n"
        f"💵 Наличные: **{p['money']} ₽** | 🏦 Банк: **{p['bank']} ₽**\n"
        f"🚨 Розыск: **`{p['wanted']}/6`** | 🧾 Штрафы: **{p['fines']} ₽**\n"
        f"🏛 Фракция: **{fac_name}** (ранг `{p['rank']}/10`){role_tag}\n"
        f"🚗 Авто: {cars_txt}\n"
        f"🏠 Недвижимость: {houses_txt}",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("work"))
@dp.message(F.text == "💵 Работа")
async def cmd_work(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    now = time.time()
    cooldown = 30
    left = int(cooldown - (now - float(p.get("last_work", 0.0))))
    if left > 0:
        await safe_answer(message, f"⏳ Отдохните ещё **{left} сек.** перед следующей сменой.", parse_mode="Markdown")
        return

    base = 1200 + (p["lvl"] - 1) * 200
    fac_key = p.get("faction", "none")
    if fac_key in FACTIONS:
        base += int(FACTIONS[fac_key]["salary"] * (1 + (p["rank"] - 1) * 0.1))

    car_bonus = sum(SHOP_CARS[c]["bonus_work"] for c in p["cars"] if c in SHOP_CARS)
    reward = base + car_bonus + random.randint(100, 400)

    p["money"] += reward
    p["xp"] += 25
    p["last_work"] = now
    if p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()

    await safe_answer(message, 
        f"💼 Смена завершена! Вы заработали **+{reward} ₽** и **+25 XP**.\n"
        f"Наличные: **{p['money']} ₽** | Уровень: **{p['lvl']}**",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


# --- ПРОМОКОДЫ ---

@dp.message(Command("addpromo"))
async def cmd_addpromo(message: Message):
    uid = message.from_user.id
    if not (is_admin(uid, 3) or is_media(uid)):
        await safe_answer(message, "⛔ Создавать промокоды можно с 3 ранга администратора или с ролью медиа.")
        return

    parts = (message.text or "").split()
    if len(parts) not in (4, 5):
        await safe_answer(message, 
            "Формат: `/addpromo <КОД> <сумма> <активаций>` или `/addpromo <КОД> <сумма> <xp> <активаций>`",
            parse_mode="Markdown",
        )
        return

    code = parts[1].strip().upper()
    try:
        if len(parts) == 4:
            amount = int(parts[2])
            xp_bonus = 0
            uses = int(parts[3])
        else:
            amount = int(parts[2])
            xp_bonus = int(parts[3])
            uses = int(parts[4])
    except ValueError:
        await safe_answer(message, "Числовые параметры указаны некорректно.")
        return

    if not code or len(code) > 24:
        await safe_answer(message, "Код должен быть длиной от 1 до 24 символов.")
        return
    if not (0 <= amount <= 500000) or not (0 <= xp_bonus <= 5000) or not (1 <= uses <= 100000):
        await safe_answer(message, "Лимиты: сумма 0..500 000 ₽, XP 0..5 000, активаций 1..100 000.")
        return
    if amount == 0 and xp_bonus == 0:
        await safe_answer(message, "Промокод должен выдавать хотя бы деньги или XP.")
        return

    promocodes[code] = {
        "code": code,
        "money": amount,
        "xp": xp_bonus,
        "uses_left": uses,
        "used_by": [],
    }
    save_state()
    await safe_answer(message, 
        f"🎟 Промокод **`{code}`** создан!\n"
        f"💵 Деньги: **{amount} ₽** | ⭐ XP: **{xp_bonus}** | Активаций: **{uses}**",
        parse_mode="Markdown",
    )


@dp.message(Command("delpromo"))
async def cmd_delpromo(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 3):
        await safe_answer(message, "⛔ Удалять промокоды можно с 3 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/delpromo <КОД>`", parse_mode="Markdown")
        return
    code = parts[1].strip().upper()
    if code not in promocodes:
        await safe_answer(message, "Промокод не найден.")
        return
    del promocodes[code]
    save_state()
    await safe_answer(message, f"🗑 Промокод **`{code}`** удалён.", parse_mode="Markdown")


@dp.message(Command("promo"))
async def cmd_promo(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/promo <КОД>`", parse_mode="Markdown")
        return

    code = parts[1].strip().upper()
    promo = promocodes.get(code)
    if not promo or int(promo.get("uses_left", 0)) <= 0:
        await safe_answer(message, "❌ Промокод не существует или активации закончились.")
        return

    used_by = promo.setdefault("used_by", [])
    if uid in used_by:
        await safe_answer(message, "⚠️ Вы уже активировали этот промокод.")
        return

    money_rew = int(promo.get("money", 0))
    xp_rew = int(promo.get("xp", 0))
    promo["uses_left"] = int(promo["uses_left"]) - 1
    used_by.append(uid)

    p["money"] += money_rew
    p["xp"] += xp_rew
    while p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()

    await safe_answer(message, 
        f"🎉 Промокод **`{code}`** активирован!\n"
        f"Награда: **+{money_rew} ₽**, **+{xp_rew} XP**.",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


# --- СОСТАВ ФРАКЦИИ ---

@dp.message(Command("members"))
async def cmd_members(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()

    if len(parts) >= 2:
        if not is_admin(uid, 2):
            await safe_answer(message, "⛔ Просматривать состав любой фракции можно со 2 ранга администратора.")
            return
        fid = parts[1].strip().lower()
    else:
        fid = p.get("faction", "none")
        if fid == "none":
            await safe_answer(message, "Вы не состоите во фракции. Укажите ключ: `/members <фракция>`", parse_mode="Markdown")
            return

    if fid not in FACTIONS:
        keys_str = ", ".join(f"`{k}`" for k in FACTIONS)
        await safe_answer(message, f"Неизвестная фракция. Доступные ключи: {keys_str}", parse_mode="Markdown")
        return

    roster = []
    for k, u in users.items():
        if isinstance(u, dict) and u.get("faction") == fid:
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                tg_id = 0
            if tg_id:
                normalize_player(u, tg_id)
            r_val = 10 if u.get("leader_of") == fid else int(u.get("rank", 1))
            roster.append((r_val, str(u.get("name", "Игрок")), int(u.get("game_id", 0)), int(u.get("wanted", 0))))

    roster.sort(key=lambda item: (-item[0], item[1].lower()))
    fac_name = FACTIONS[fid]["name"]

    if not roster:
        await safe_answer(message, f"👥 В фракции **{fac_name}** сейчас никого нет.", parse_mode="Markdown")
        return

    lines = [f"👥 **Состав фракции «{fac_name}»** (`{len(roster)}` чел.):\n"]
    for idx, (r_val, uname, gid, w_lvl) in enumerate(roster, start=1):
        leader_tag = " 👑 Лидер" if r_val == 10 else ""
        wanted_tag = f" 🚨`{w_lvl}`" if w_lvl > 0 else ""
        lines.append(f"{idx}. **{uname}** (`#{gid}`) — ранг `{r_val}/10`{leader_tag}{wanted_tag}")

    await safe_answer(message, "\n".join(lines), parse_mode="Markdown")


# --- ДПС / ППС / ФСБ: РОЗЫСК И ШТРАФЫ ---

@dp.message(Command("wanted"))
async def cmd_wanted(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Команда доступна сотрудникам ДПС / ППС / ФСБ и администрации.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/wanted <игровой_ID> <уровень_1..6>`", parse_mode="Markdown")
        return

    try:
        target_gid = int(parts[1])
        stars = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень розыска должны быть числами.")
        return

    if not (1 <= stars <= 6):
        await safe_answer(message, "Уровень розыска должен быть от 1 до 6.")
        return

    target = find_player_by_game_id(target_gid)
    if not target:
        await safe_answer(message, f"Игрок с ID `#{target_gid}` не найден.", parse_mode="Markdown")
        return

    target["wanted"] = stars
    save_state()
    await safe_answer(message, 
        f"🚨 Игроку **{target['name']}** (`#{target_gid}`) выдан розыск: **`{stars}/6`**.",
        parse_mode="Markdown",
    )


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Команда доступна сотрудникам ДПС / ППС / ФСБ и администрации.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/clear <игровой_ID>`", parse_mode="Markdown")
        return

    try:
        target_gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return

    target = find_player_by_game_id(target_gid)
    if not target:
        await safe_answer(message, f"Игрок с ID `#{target_gid}` не найден.", parse_mode="Markdown")
        return

    target["wanted"] = 0
    save_state()
    await safe_answer(message, f"✅ С игрока **{target['name']}** (`#{target_gid}`) снят розыск.", parse_mode="Markdown")


@dp.message(Command("fine"))
async def cmd_fine(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Выписывать штрафы могут сотрудники ДПС / ППС / ФСБ и администрация.")
        return

    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        await safe_answer(message, "Формат: `/fine <игровой_ID> <сумма> [причина]`", parse_mode="Markdown")
        return

    try:
        target_gid = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и сумма штрафа должны быть числами.")
        return

    if not (100 <= amount <= 250000):
        await safe_answer(message, "Сумма штрафа должна быть от 100 до 250 000 ₽.")
        return

    reason = parts[3].strip() if len(parts) == 4 else "Нарушение ПДД / общественного порядка"
    target = find_player_by_game_id(target_gid)
    if not target:
        await safe_answer(message, f"Игрок с ID `#{target_gid}` не найден.", parse_mode="Markdown")
        return

    if target["money"] >= amount:
        target["money"] -= amount
        paid_msg = f"списано **{amount} ₽** наличными"
    elif target["bank"] >= amount:
        target["bank"] -= amount
        paid_msg = f"списано **{amount} ₽** с банковского счёта"
    else:
        target["fines"] = int(target.get("fines", 0)) + amount
        paid_msg = f"добавлено в неоплаченные штрафы (**+{amount} ₽**)"

    actor["money"] += max(100, int(amount * 0.2))
    save_state()

    await safe_answer(message, 
        f"🧾 Выписан штраф игроку **{target['name']}** (`#{target_gid}`) на **{amount} ₽** ({paid_msg}).\n"
        f"Причина: _{reason}_",
        parse_mode="Markdown",
    )


# --- БИЗНЕСЫ (ВКЛЮЧАЯ ПРОДАЖУ В ГОС) ---

@dp.message(F.text == "🏢 Бизнесы")
async def btn_biz(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    await render_biz_menu(message, uid, edit=False)


async def render_biz_menu(target_msg: Message, uid: int, edit: bool = False):
    now = time.time()
    lines = ["🏢 **Бизнесы Criminal Russia:**\n"]
    kb_rows: list[list[InlineKeyboardButton]] = []

    for bid, b in businesses.items():
        income_hr = int(b.get("income_per_hour", 0))
        owner_uid = b.get("owner_uid")
        if owner_uid == uid:
            last_col = float(b.get("last_collect", 0.0))
            elapsed_hr = max(0.0, (now - last_col) / 3600.0) if last_col > 0 else 0.0
            pending = int(b.get("cash", 0)) + int(elapsed_hr * income_hr)
            lines.append(
                f"• **{b['name']}** *(Ваш бизнес)* — доход `{income_hr} ₽/ч`, к сбору: **{pending} ₽**"
            )
            refund = int(int(b["price"]) * 0.7)
            kb_rows.append([
                InlineKeyboardButton(text=f"💰 Собрать ({pending} ₽)", callback_data=f"biz_take:{bid}"),
                InlineKeyboardButton(text=f"🏷 Продать ({refund} ₽)", callback_data=f"biz_sell:{bid}"),
            ])
        elif owner_uid is None:
            lines.append(f"• **{b['name']}** — цена **{b['price']} ₽**, доход `{income_hr} ₽/ч` *(Свободен)*")
            kb_rows.append([
                InlineKeyboardButton(text=f"🛒 Купить {b['name']}", callback_data=f"biz_buy:{bid}")
            ])
        else:
            lines.append(
                f"• **{b['name']}** — владелец: **{b.get('owner_name') or 'Игрок'}**, доход `{income_hr} ₽/ч`"
            )

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None
    text = "\n".join(lines)
    if edit:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("biz_buy:"))
async def cb_biz_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    bid = callback.data.split(":", 1)[1]
    b = businesses.get(bid)
    if not b:
        await callback.answer("Бизнес не найден", show_alert=True)
        return
    if b.get("owner_uid") is not None:
        await callback.answer("Бизнес уже занят", show_alert=True)
        return
    price = int(b["price"])
    if p["money"] < price:
        await callback.answer(f"Не хватает наличных (нужно {price} ₽)", show_alert=True)
        return

    p["money"] -= price
    b["owner_uid"] = uid
    b["owner_name"] = p["name"]
    b["cash"] = 0
    b["last_collect"] = time.time()
    save_state()

    await callback.answer(f"Вы купили «{b['name']}»!", show_alert=True)
    if callback.message:
        await render_biz_menu(callback.message, uid, edit=True)


@dp.callback_query(F.data.startswith("biz_take:"))
async def cb_biz_take(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    bid = callback.data.split(":", 1)[1]
    b = businesses.get(bid)
    if not b or b.get("owner_uid") != uid:
        await callback.answer("Это не ваш бизнес", show_alert=True)
        return

    now = time.time()
    last_col = float(b.get("last_collect", 0.0))
    elapsed_hr = max(0.0, (now - last_col) / 3600.0) if last_col > 0 else 0.0
    total = int(b.get("cash", 0)) + int(elapsed_hr * int(b.get("income_per_hour", 0)))
    if total <= 0:
        total = min(int(b.get("income_per_hour", 1000)), 2500)

    p["money"] += total
    b["cash"] = 0
    b["last_collect"] = now
    save_state()

    await callback.answer(f"Собрано +{total} ₽!", show_alert=True)
    if callback.message:
        await render_biz_menu(callback.message, uid, edit=True)


@dp.callback_query(F.data.startswith("biz_sell:"))
async def cb_biz_sell(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    bid = callback.data.split(":", 1)[1]
    b = businesses.get(bid)
    if not b or b.get("owner_uid") != uid:
        await callback.answer("Это не ваш бизнес", show_alert=True)
        return

    refund = int(int(b["price"]) * 0.7)
    p["money"] += refund
    b["owner_uid"] = None
    b["owner_name"] = None
    b["cash"] = 0
    b["last_collect"] = 0.0
    save_state()

    await callback.answer(f"Бизнес продан за {refund} ₽!", show_alert=True)
    if callback.message:
        await render_biz_menu(callback.message, uid, edit=True)


# --- ХЕЛПЕРЫ И СИСТЕМА ПОДДЕРЖКИ ---

async def notify_staff_ticket(bot: Bot, ticket_id: str, text_msg: str) -> None:
    targets: set[int] = set()
    if CREATOR_ID:
        targets.add(CREATOR_ID)
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            if int(u.get("admin_lvl", 0)) >= 1 or int(u.get("helper_lvl", 0)) >= 1:
                targets.add(tg_id)

    for staff_id in targets:
        try:
            await safe_send(bot, staff_id, text_msg, parse_mode="Markdown")
        except Exception:
            pass


@dp.message(Command("support"))
@dp.message(F.text == "🎫 Поддержка")
async def cmd_support(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 2 and parts[1].strip():
        await create_support_ticket(message, bot, p, parts[1].strip())
        return

    await state.set_state(SupportStates.waiting_message)
    await safe_answer(message, 
        "🎫 **Служба поддержки**\n"
        "Напишите ваш вопрос или описание проблемы одним сообщением — хелперы или администраторы ответят вам.\n"
        "Для отмены отправьте `/cancel`.",
        parse_mode="Markdown",
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    cur = await state.get_state()
    if cur is None:
        await safe_answer(message, "Нет активного действия для отмены.", reply_markup=main_kb(message.from_user.id))
        return
    await state.clear()
    await safe_answer(message, "Действие отменено.", reply_markup=main_kb(message.from_user.id))


@dp.message(SupportStates.waiting_message)
async def process_support_text(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    text_body = (message.text or "").strip()
    if not text_body:
        await safe_answer(message, "Пожалуйста, напишите текстовое сообщение или отправьте `/cancel`.")
        return
    await state.clear()
    await create_support_ticket(message, bot, p, text_body)


async def create_support_ticket(message: Message, bot: Bot, p: dict[str, Any], body: str) -> None:
    global next_ticket_id
    tid = str(next_ticket_id)
    next_ticket_id += 1

    uid = int(p["tg_id"])
    support_tickets[tid] = {
        "id": tid,
        "user_id": uid,
        "game_id": int(p["game_id"]),
        "user_name": str(p["name"]),
        "status": "open",
        "created_at": int(time.time()),
        "messages": [{"from": "player", "name": str(p["name"]), "text": body}],
    }
    p["active_ticket"] = tid
    save_state()

    await safe_answer(message, 
        f"✅ Обращение **`#{tid}`** отправлено в поддержку! Ожидайте ответа.",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await notify_staff_ticket(
        bot,
        tid,
        f"🎫 **Новый тикет `#{tid}`**\n"
        f"Игрок: **{p['name']}** (`#{p['game_id']}`, TG: `{uid}`)\n"
        f"Текст: {body}\n"
        f"Ответить: `/answer {tid} <текст>`",
    )


@dp.message(Command("tickets"))
@dp.message(F.text == "🛟 Хелперка")
async def cmd_tickets(message: Message):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Раздел доступен только хелперам и администрации.")
        return

    open_list = [t for t in support_tickets.values() if isinstance(t, dict) and t.get("status") == "open"]
    if not open_list:
        await safe_answer(message, "🛟 Открытых обращений в поддержку сейчас нет.", reply_markup=main_kb(uid))
        return

    lines = [f"🛟 **Открытые тикеты** (`{len(open_list)}`):\n"]
    for t in open_list[:20]:
        msgs = t.get("messages") or []
        last_txt = msgs[-1].get("text", "") if msgs else ""
        lines.append(
            f"• Тикет **`#{t['id']}`** — **{t.get('user_name')}** (`#{t.get('game_id')}`)\n"
            f"  _{last_txt[:100]}_"
        )
    lines.append("\nКоманды: `/answer <ID> <текст>` | `/closeticket <ID>`")
    await safe_answer(message, "\n".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(Command("answer"))
async def cmd_answer_ticket(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Отвечать на тикеты могут хелперы и администраторы.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await safe_answer(message, "Формат: `/answer <ID_тикета> <текст ответа>`", parse_mode="Markdown")
        return

    tid = parts[1].lstrip("#").strip()
    reply_text = parts[2].strip()
    ticket = support_tickets.get(tid)
    if not ticket:
        await safe_answer(message, f"Тикет `#{tid}` не найден.", parse_mode="Markdown")
        return

    staff = get_player(uid, message.from_user.full_name)
    ticket.setdefault("messages", []).append({
        "from": "staff",
        "name": staff["name"],
        "text": reply_text,
    })
    save_state()

    target_uid = int(ticket["user_id"])
    try:
        await safe_send(bot, 
            target_uid,
            f"💬 **Ответ поддержки по тикету `#{tid}`** ({staff['name']}):\n{reply_text}",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await safe_answer(message, f"✅ Ответ по тикету `#{tid}` отправлен игроку.", parse_mode="Markdown")


@dp.message(Command("closeticket"))
async def cmd_close_ticket(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Закрывать тикеты могут хелперы и администраторы.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/closeticket <ID_тикета>`", parse_mode="Markdown")
        return

    tid = parts[1].lstrip("#").strip()
    ticket = support_tickets.get(tid)
    if not ticket:
        await safe_answer(message, f"Тикет `#{tid}` не найден.", parse_mode="Markdown")
        return

    ticket["status"] = "closed"
    save_state()

    target_uid = int(ticket["user_id"])
    u = users.get(str(target_uid))
    if isinstance(u, dict) and u.get("active_ticket") == tid:
        u["active_ticket"] = None
        save_state()

    try:
        await safe_send(bot, 
            target_uid,
            f"🔒 Ваш тикет в поддержку `#{tid}` закрыт. Если появятся новые вопросы — напишите `/support`.",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await safe_answer(message, f"🔒 Тикет `#{tid}` закрыт.", parse_mode="Markdown")


# --- МЕДИА И АДМИНИСТРИРОВАНИЕ ---

@dp.message(Command("mediaprize"))
async def cmd_mediaprize(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_media(uid):
        await safe_answer(message, "⛔ Команда доступна только медиа-партнёрам.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/mediaprize <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и сумма должны быть числами.")
        return
    if not (1 <= amount <= 15000):
        await safe_answer(message, "Сумма медиа-приза должна быть от 1 до 15 000 ₽.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["money"] += amount
    save_state()
    await safe_answer(message, f"🎬 Выдан медиа-приз **+{amount} ₽** игроку **{target['name']}** (`#{gid}`).", parse_mode="Markdown")
    try:
        await safe_send(bot, int(target["tg_id"]), f"🎬 Вы получили медиа-приз **+{amount} ₽**!", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("announce"))
async def cmd_announce(message: Message, bot: Bot):
    uid = message.from_user.id
    if not (is_media(uid) or is_admin(uid, 1)):
        await safe_answer(message, "⛔ Команда доступна медиа и администрации.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await safe_answer(message, "Формат: `/announce <текст>`", parse_mode="Markdown")
        return
    header = "📢 **ОБЪЯВЛЕНИЕ АДМИНИСТРАЦИИ**" if is_admin(uid, 1) else "🎬 **МЕДИА-ОБЪЯВЛЕНИЕ**"
    body = f"{header}\n\n{parts[1].strip()}"
    sent = 0
    for k in list(users.keys()):
        try:
            await safe_send(bot, int(k), body, parse_mode="Markdown")
            sent += 1
        except Exception:
            pass
    await safe_answer(message, f"✅ Объявление отправлено `{sent}` игрокам.", parse_mode="Markdown")


@dp.message(Command("players"))
async def cmd_players(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 1):
        await safe_answer(message, "⛔ Команда доступна с 1 ранга администратора.")
        return
    if not users:
        await safe_answer(message, "Игроков пока нет.")
        return
    items = []
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            items.append(normalize_player(u, tg_id))
    items.sort(key=lambda x: int(x.get("game_id", 0)))
    lines = [f"📋 **Игроки** (всего: `{len(items)}`):\n"]
    for u in items[:40]:
        ban_tag = " 🚫" if u.get("banned") else ""
        lines.append(
            f"• **`#{u['game_id']}`** {u['name']} — {u['lvl']} ур. | {u['money'] + u['bank']} ₽{ban_tag}"
        )
    await safe_answer(message, "\n".join(lines), parse_mode="Markdown")


@dp.message(Command("sethelper"))
async def cmd_sethelper(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Назначать хелперов можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/sethelper <игровой_ID> <0..3>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        lvl = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень должны быть числами.")
        return
    if not (0 <= lvl <= 3):
        await safe_answer(message, "Уровень хелпера должен быть от 0 до 3.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["helper_lvl"] = lvl
    save_state()
    await safe_answer(message, f"🛟 Игроку **{target['name']}** (`#{gid}`) установлен уровень хелпера: **`{lvl}`**.", parse_mode="Markdown")


@dp.message(Command("setmedia"))
async def cmd_setmedia(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Выдавать роль медиа можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/setmedia <игровой_ID> <0|1>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        val = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и значение должны быть числами.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["is_media"] = bool(val)
    save_state()
    await safe_answer(message, f"🎬 Роль медиа для **{target['name']}** (`#{gid}`): **`{bool(val)}`**.", parse_mode="Markdown")


@dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 5):
        await safe_answer(message, "⛔ Назначать администраторов может только 5 ранг / создатель.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/setadmin <игровой_ID> <0..5>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        lvl = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень должны быть числами.")
        return
    if not (0 <= lvl <= 5):
        await safe_answer(message, "Уровень администратора должен быть от 0 до 5.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["admin_lvl"] = lvl
    save_state()
    await safe_answer(message, f"🛡 Игроку **{target['name']}** (`#{gid}`) выдан уровень админа: **`{lvl}`**.", parse_mode="Markdown")


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Банить игроков можно со 2 ранга администратора.")
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await safe_answer(message, "Формат: `/ban <игровой_ID> [причина]`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    if is_creator(int(target["tg_id"])):
        await safe_answer(message, "Нельзя заблокировать создателя.")
        return
    target["banned"] = True
    target["ban_reason"] = parts[2].strip() if len(parts) == 3 else "Нарушение правил сервера"
    save_state()
    await safe_answer(message, f"🚫 Игрок **{target['name']}** (`#{gid}`) заблокирован.", parse_mode="Markdown")


@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Разбанивать игроков можно со 2 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/unban <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["banned"] = False
    target["ban_reason"] = ""
    save_state()
    await safe_answer(message, f"✅ Игрок **{target['name']}** (`#{gid}`) разблокирован.", parse_mode="Markdown")


# --- ДОПОЛНИТЕЛЬНЫЕ КНОПКИ, ФРАКЦИИ, СЕМЬЯ, МАГАЗИНЫ, ТОП И АДМИНКА ---

def get_family_by_id(fid: Any) -> dict[str, Any] | None:
    if not fid:
        return None
    return families.get(str(fid))


def get_player_family(p: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    uid = int(p.get("tg_id", 0))
    fam_id = p.get("family_id")
    if fam_id and str(fam_id) in families:
        return str(fam_id), families[str(fam_id)]
    for k, fdata in families.items():
        if isinstance(fdata, dict):
            members = fdata.get("members") or []
            if fdata.get("owner_uid") == uid or uid in members:
                p["family_id"] = str(k)
                return str(k), fdata
    return None, None


@dp.message(F.text == "🏠 Недвижимость")
async def btn_houses(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    await render_houses_menu(message, uid, edit=False)


async def render_houses_menu(target_msg: Message, uid: int, edit: bool = False):
    p = get_player(uid)
    owned = set(p.get("houses") or [])
    lines = ["🏠 **Недвижимость Criminal Russia:**\n"]
    rows: list[list[InlineKeyboardButton]] = []
    for hid, h in SHOP_HOUSES.items():
        has_it = hid in owned
        status = "*(В собственности)*" if has_it else f"цена **{h['price']} ₽**"
        lines.append(f"• **{h['name']}** — {status}, бонус банка: `+{h['bonus_bank']} ₽/смена`")
        if has_it:
            refund = int(int(h["price"]) * 0.7)
            rows.append([
                InlineKeyboardButton(text=f"🏷 Продать {h['name']} ({refund} ₽)", callback_data=f"house_sell:{hid}")
            ])
        else:
            rows.append([
                InlineKeyboardButton(text=f"🛒 Купить {h['name']}", callback_data=f"house_buy:{hid}")
            ])
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    text = "\n".join(lines)
    if edit:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("house_buy:"))
async def cb_house_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    hid = callback.data.split(":", 1)[1]
    h = SHOP_HOUSES.get(hid)
    if not h:
        await callback.answer("Недвижимость не найдена", show_alert=True)
        return
    if hid in p["houses"]:
        await callback.answer("У вас уже есть эта недвижимость", show_alert=True)
        return
    price = int(h["price"])
    if p["money"] < price:
        await callback.answer(f"Не хватает наличных (нужно {price} ₽)", show_alert=True)
        return
    p["money"] -= price
    p["houses"].append(hid)
    save_state()
    await callback.answer(f"Куплено: {h['name']}!", show_alert=True)
    if callback.message:
        await render_houses_menu(callback.message, uid, edit=True)


@dp.callback_query(F.data.startswith("house_sell:"))
async def cb_house_sell(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    hid = callback.data.split(":", 1)[1]
    h = SHOP_HOUSES.get(hid)
    if not h or hid not in p["houses"]:
        await callback.answer("У вас нет этой недвижимости", show_alert=True)
        return
    refund = int(int(h["price"]) * 0.7)
    p["houses"].remove(hid)
    p["money"] += refund
    save_state()
    await callback.answer(f"Продано за {refund} ₽!", show_alert=True)
    if callback.message:
        await render_houses_menu(callback.message, uid, edit=True)


@dp.message(F.text == "🚗 Автосалон")
async def btn_cars(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    await render_cars_menu(message, uid, edit=False)


async def render_cars_menu(target_msg: Message, uid: int, edit: bool = False):
    p = get_player(uid)
    owned = set(p.get("cars") or [])
    lines = ["🚗 **Автосалон Criminal Russia:**\n"]
    rows: list[list[InlineKeyboardButton]] = []
    for cid, c in SHOP_CARS.items():
        has_it = cid in owned
        status = "*(В гараже)*" if has_it else f"цена **{c['price']} ₽**"
        lines.append(f"• **{c['name']}** — {status}, бонус смены: `+{c['bonus_work']} ₽`")
        if has_it:
            refund = int(int(c["price"]) * 0.7)
            rows.append([
                InlineKeyboardButton(text=f"🏷 Продать {c['name']} ({refund} ₽)", callback_data=f"car_sell:{cid}")
            ])
        else:
            rows.append([
                InlineKeyboardButton(text=f"🛒 Купить {c['name']}", callback_data=f"car_buy:{cid}")
            ])
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    text = "\n".join(lines)
    if edit:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("car_buy:"))
async def cb_car_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    cid = callback.data.split(":", 1)[1]
    c = SHOP_CARS.get(cid)
    if not c:
        await callback.answer("Авто не найдено", show_alert=True)
        return
    if cid in p["cars"]:
        await callback.answer("Это авто уже есть в гараже", show_alert=True)
        return
    price = int(c["price"])
    if p["money"] < price:
        await callback.answer(f"Не хватает наличных (нужно {price} ₽)", show_alert=True)
        return
    p["money"] -= price
    p["cars"].append(cid)
    save_state()
    await callback.answer(f"Куплено авто: {c['name']}!", show_alert=True)
    if callback.message:
        await render_cars_menu(callback.message, uid, edit=True)


@dp.callback_query(F.data.startswith("car_sell:"))
async def cb_car_sell(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    cid = callback.data.split(":", 1)[1]
    c = SHOP_CARS.get(cid)
    if not c or cid not in p["cars"]:
        await callback.answer("Этого авто нет у вас", show_alert=True)
        return
    refund = int(int(c["price"]) * 0.7)
    p["cars"].remove(cid)
    p["money"] += refund
    save_state()
    await callback.answer(f"Авто продано за {refund} ₽!", show_alert=True)
    if callback.message:
        await render_cars_menu(callback.message, uid, edit=True)


@dp.message(F.text == "👨‍👩‍👧‍👦 Семья")
async def btn_family(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid, fdata = get_player_family(p)
    if not fid or not fdata:
        await safe_answer(message, 
            "👨‍👩‍👧‍👦 **Семьи**\n"
            "Вы пока не состоите в семье.\n"
            "Создать семью (стоимость `50 000 ₽`): `/createfam <Название>`",
            reply_markup=main_kb(uid),
            parse_mode="Markdown",
        )
        return

    members = list(fdata.get("members") or [])
    if uid not in members:
        members.append(uid)
        fdata["members"] = members
    balance = int(fdata.get("balance", 0))
    owner_name = fdata.get("owner_name") or "Глава"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Вложить 5 000 ₽", callback_data=f"fam_dep:{fid}:5000"),
            InlineKeyboardButton(text="💸 Снять 5 000 ₽", callback_data=f"fam_take:{fid}:5000"),
        ],
        [InlineKeyboardButton(text="🚪 Покинуть семью", callback_data=f"fam_leave:{fid}")],
    ])
    await safe_answer(message, 
        f"👨‍👩‍👧‍👦 **Семья «{fdata.get('name', fid)}»** (`#{fid}`)\n"
        f"👑 Глава: **{owner_name}** | Участников: **`{len(members)}`**\n"
        f"🏦 Общак семьи: **{balance} ₽**",
        reply_markup=kb,
        parse_mode="Markdown",
    )


@dp.message(Command("createfam"))
async def cmd_createfam(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid, _ = get_player_family(p)
    if fid:
        await safe_answer(message, "Вы уже состоите в семье. Сначала выйдите из текущей.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await safe_answer(message, "Формат: `/createfam <Название семьи>`", parse_mode="Markdown")
        return
    fam_name = parts[1].strip()[:32]
    cost = 50000
    if p["money"] < cost:
        await safe_answer(message, f"Для создания семьи нужно **{cost} ₽** наличными.", parse_mode="Markdown")
        return

    new_id = str(len(families) + 1)
    while new_id in families:
        new_id = str(int(new_id) + 1)

    p["money"] -= cost
    p["family_id"] = new_id
    families[new_id] = {
        "id": new_id,
        "name": fam_name,
        "owner_uid": uid,
        "owner_name": p["name"],
        "members": [uid],
        "balance": 0,
    }
    save_state()
    await safe_answer(message, f"🎉 Семья **«{fam_name}»** (`#{new_id}`) создана!", reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.callback_query(F.data.startswith("fam_dep:"))
async def cb_fam_dep(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    _, fid, amt_s = callback.data.split(":", 2)
    amt = int(amt_s)
    fdata = families.get(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if p["money"] < amt:
        await callback.answer(f"Не хватает {amt} ₽ наличными", show_alert=True)
        return
    p["money"] -= amt
    fdata["balance"] = int(fdata.get("balance", 0)) + amt
    save_state()
    await callback.answer(f"Вложено +{amt} ₽ в общак!", show_alert=True)


@dp.callback_query(F.data.startswith("fam_take:"))
async def cb_fam_take(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    _, fid, amt_s = callback.data.split(":", 2)
    amt = int(amt_s)
    fdata = families.get(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if int(fdata.get("balance", 0)) < amt:
        await callback.answer("В общаке недостаточно средств", show_alert=True)
        return
    fdata["balance"] = int(fdata.get("balance", 0)) - amt
    p["money"] += amt
    save_state()
    await callback.answer(f"Снято +{amt} ₽ из общака!", show_alert=True)


@dp.callback_query(F.data.startswith("fam_leave:"))
async def cb_fam_leave(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = families.get(fid)
    if fdata:
        members = list(fdata.get("members") or [])
        if uid in members:
            members.remove(uid)
            fdata["members"] = members
        if fdata.get("owner_uid") == uid:
            if members:
                fdata["owner_uid"] = members[0]
                next_u = users.get(str(members[0]))
                fdata["owner_name"] = next_u.get("name") if isinstance(next_u, dict) else "Глава"
            else:
                del families[fid]
    p["family_id"] = None
    save_state()
    await callback.answer("Вы вышли из семьи", show_alert=True)


@dp.message(F.text == "🏛 Фракции")
async def btn_factions(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    cur_fac = p.get("faction", "none")
    cur_title = FACTIONS[cur_fac]["name"] if cur_fac in FACTIONS else "Нет"

    lines = [
        f"🏛 **Фракции Criminal Russia** (текущая: **{cur_title}**)\n"
        "Подайте заявку на вступление или выполните задание у NPC:\n"
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for fid, fdata in FACTIONS.items():
        lines.append(
            f"• **{fdata['name']}** (`{fid}`) — оклад `{fdata['salary']} ₽`, NPC: *{fdata['npc']}*"
        )
        rows.append([
            InlineKeyboardButton(text=f"📝 Заявка в {fdata['name']}", callback_data=f"fac_apply:{fid}"),
            InlineKeyboardButton(text=f"🤖 NPC ({fid})", callback_data=f"fac_npc:{fid}"),
        ])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await safe_answer(message, "\n".join(lines), reply_markup=kb, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("fac_apply:"))
async def cb_fac_apply(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if fid not in FACTIONS:
        await callback.answer("Фракция не найдена", show_alert=True)
        return
    if p.get("faction") == fid:
        await callback.answer("Вы уже состоите в этой фракции", show_alert=True)
        return

    app_id = f"{uid}_{fid}"
    faction_apps[app_id] = {
        "id": app_id,
        "uid": uid,
        "game_id": p["game_id"],
        "name": p["name"],
        "faction": fid,
        "status": "pending",
        "created_at": int(time.time()),
    }
    save_state()
    await callback.answer(f"Заявка в «{FACTIONS[fid]['name']}» отправлена!", show_alert=True)


@dp.callback_query(F.data.startswith("fac_npc:"))
async def cb_fac_npc(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = FACTIONS.get(fid)
    if not fdata:
        await callback.answer("Фракция не найдена", show_alert=True)
        return
    now = time.time()
    left = int(60 - (now - float(p.get("last_npc", 0.0))))
    if left > 0:
        await callback.answer(f"NPC занят, подождите {left} сек.", show_alert=True)
        return

    reward = random.randint(1500, 3500)
    p["money"] += reward
    p["xp"] += 30
    p["last_npc"] = now
    if p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()
    await callback.answer(f"{fdata['npc']}: +{reward} ₽ и +30 XP!", show_alert=True)


@dp.message(Command("r"))
async def cmd_faction_chat(message: Message, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    if fid not in FACTIONS:
        await safe_answer(message, "Вы не состоите во фракции.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await safe_answer(message, "Формат: `/r <сообщение>`", parse_mode="Markdown")
        return
    msg_txt = f"📡 **[{FACTIONS[fid]['name']}] {p['name']} (`#{p['game_id']}`):** {parts[1].strip()}"
    sent = 0
    for k, u in users.items():
        if isinstance(u, dict) and u.get("faction") == fid:
            try:
                await safe_send(bot, int(k), msg_txt, parse_mode="Markdown")
                sent += 1
            except Exception:
                pass
    await safe_answer(message, f"✅ Отправлено в рацию (`{sent}` чел.).", parse_mode="Markdown")


@dp.message(Command("invite"))
async def cmd_invite(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 8 and actor.get("faction") in FACTIONS else None)
    if not fid:
        await safe_answer(message, "⛔ Принимать во фракцию могут только лидеры или старший состав (8+ ранг).")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/invite <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["faction"] = fid
    target["rank"] = 1
    save_state()
    await safe_answer(message, f"✅ Игрок **{target['name']}** (`#{gid}`) принят в **{FACTIONS[fid]['name']}**.", parse_mode="Markdown")
    try:
        await safe_send(bot, int(target["tg_id"]), f"🏛 Вы приняты во фракцию **«{FACTIONS[fid]['name']}»**!", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("uninvite"))
async def cmd_uninvite(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of")
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Увольнять из фракции могут лидеры или админы 3+ ранга.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/uninvite <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    if fid and target.get("faction") != fid:
        await safe_answer(message, "Игрок не состоит в вашей фракции.")
        return
    target["faction"] = "none"
    target["rank"] = 1
    target["leader_of"] = None
    save_state()
    await safe_answer(message, f"🗑 Игрок **{target['name']}** (`#{gid}`) уволен из фракции.", parse_mode="Markdown")


@dp.message(Command("setrank"))
async def cmd_setrank(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of")
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Менять ранги могут лидеры или админы 3+ ранга.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/setrank <игровой_ID> <1..10>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        rk = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и ранг должны быть числами.")
        return
    if not (1 <= rk <= 10):
        await safe_answer(message, "Ранг должен быть от 1 до 10.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    if fid and target.get("faction") != fid:
        await safe_answer(message, "Игрок не состоит в вашей фракции.")
        return
    target["rank"] = rk
    save_state()
    await safe_answer(message, f"⭐ Игроку **{target['name']}** (`#{gid}`) установлен ранг **`{rk}/10`**.", parse_mode="Markdown")


@dp.message(Command("setleader"))
async def cmd_setleader(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Назначать лидеров можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/setleader <игровой_ID> <фракция|none>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    fid = parts[2].strip().lower()
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    if fid == "none":
        target["leader_of"] = None
        save_state()
        await safe_answer(message, f"✅ Лидерство у **{target['name']}** (`#{gid}`) снято.", parse_mode="Markdown")
        return
    if fid not in FACTIONS:
        await safe_answer(message, f"Неизвестная фракция. Доступно: {', '.join(FACTIONS.keys())}")
        return
    target["faction"] = fid
    target["rank"] = 10
    target["leader_of"] = fid
    save_state()
    await safe_answer(message, f"👑 **{target['name']}** (`#{gid}`) назначен лидером **«{FACTIONS[fid]['name']}»**!", parse_mode="Markdown")


@dp.message(F.text == "🏆 Топ-10")
async def btn_top(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    items = []
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            p_norm = normalize_player(u, tg_id)
            cap = int(p_norm.get("money", 0)) + int(p_norm.get("bank", 0))
            items.append((cap, int(p_norm.get("lvl", 1)), str(p_norm.get("name", "Игрок")), int(p_norm.get("game_id", 0))))
    items.sort(key=lambda x: (-x[0], -x[1]))
    lines = ["🏆 **Топ-10 богатейших игроков:**\n"]
    for idx, (cap, lvl, name, gid) in enumerate(items[:10], start=1):
        lines.append(f"{idx}. **{name}** (`#{gid}`) — **{cap} ₽** ({lvl} ур.)")
    await safe_answer(message, "\n".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")





@dp.message(Command("givemoney"))
async def cmd_givemoney(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Выдавать валюту можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: `/givemoney <игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
        amt = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и сумма должны быть числами.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["money"] += amt
    save_state()
    await safe_answer(message, f"💵 Выдано **{amt} ₽** игроку **{target['name']}** (`#{gid}`).", parse_mode="Markdown")
    try:
        await safe_send(bot, int(target["tg_id"]), f"💵 Администрация начислила вам **{amt} ₽**!", parse_mode="Markdown")
    except Exception:
        pass


@dp.message(Command("media"))
@dp.message(F.text == "🎬 Медиа")
async def cmd_media_panel(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    if not is_media(uid):
        await safe_answer(
            message,
            "⛔ Раздел доступен только медиа-партнёрам (выдача через `/setmedia <ID> 1`).",
            reply_markup=main_kb(uid),
            parse_mode="Markdown",
        )
        return
    await safe_answer(
        message,
        "🎬 **Меню Медиа-партнёра:**\n"
        "• `/mediaprize <ID> <сумма>` — выдать приз (1..15 000 ₽)\n"
        "• `/announce <текст>` — объявление игрокам\n"
        "• `/addpromo <КОД> <сумма> <активаций>` — создать промокод",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("bank"))
async def cmd_bank(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) < 3 or parts[1].lower() not in {"dep", "deposit", "put", "take", "withdraw", "get"}:
        await safe_answer(
            message,
            f"🏦 **Банковский счёт**\n"
            f"Наличные: **{p['money']} ₽** | В банке: **{p['bank']} ₽**\n"
            "Положить: `/bank put <сумма>`\n"
            "Снять: `/bank take <сумма>`",
            reply_markup=main_kb(uid),
            parse_mode="Markdown",
        )
        return
    action = parts[1].lower()
    try:
        amt = int(parts[2])
    except ValueError:
        await safe_answer(message, "Сумма должна быть числом.")
        return
    if amt <= 0:
        await safe_answer(message, "Сумма должна быть больше 0.")
        return
    if action in {"dep", "deposit", "put"}:
        if p["money"] < amt:
            await safe_answer(message, "Недостаточно наличных.")
            return
        p["money"] -= amt
        p["bank"] += amt
        save_state()
        await safe_answer(message, f"🏦 Положено в банк **+{amt} ₽**. Баланс банка: **{p['bank']} ₽**.", reply_markup=main_kb(uid), parse_mode="Markdown")
    else:
        if p["bank"] < amt:
            await safe_answer(message, "Недостаточно средств на банковском счёте.")
            return
        p["bank"] -= amt
        p["money"] += amt
        save_state()
        await safe_answer(message, f"💵 Снято с банка **+{amt} ₽**. Наличные: **{p['money']} ₽**.", reply_markup=main_kb(uid), parse_mode="Markdown")


async def main() -> None:
    load_state()
    save_state()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
