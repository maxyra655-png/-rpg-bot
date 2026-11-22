import asyncio
import json
import os
import random
import re
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

ADMIN_RANKS: dict[int, dict[str, Any]] = {
    1: {"title": "Младший администратор", "perm_desc": "Базовый надзор и просмотр игроков"},
    2: {"title": "Администратор", "perm_desc": "Баны, временные баны и просмотр составов фракций"},
    3: {"title": "Старший администратор", "perm_desc": "Промокоды, управление фракциями и выговоры"},
    4: {"title": "Куратор состава", "perm_desc": "Выдача валюты, хелперы, медиа, лидерки и техработы"},
    5: {"title": "Главный администратор", "perm_desc": "Назначение админов (до 6 ур.) и обнуление аккаунтов"},
    6: {"title": "Заместитель ГА", "perm_desc": "Назначение админов (до 7 ур.) и полный контроль персонала"},
    7: {"title": "Руководитель проекта", "perm_desc": "Назначение админов (до 8 ур.) и глобальные настройки"},
    8: {"title": "Специальный администратор", "perm_desc": "Высший административный уровень перед создателем"},
}

HELPER_RANKS: dict[int, dict[str, Any]] = {
    1: {"title": "Стажёр поддержки", "ans_bonus": 150, "xp_bonus": 10},
    2: {"title": "Младший хелпер", "ans_bonus": 250, "xp_bonus": 15},
    3: {"title": "Хелпер", "ans_bonus": 400, "xp_bonus": 20},
    4: {"title": "Старший хелпер", "ans_bonus": 600, "xp_bonus": 25},
    5: {"title": "Ведущий хелпер", "ans_bonus": 850, "xp_bonus": 35},
    6: {"title": "Инструктор хелперов", "ans_bonus": 1150, "xp_bonus": 45},
    7: {"title": "Зам. куратора хелперов", "ans_bonus": 1500, "xp_bonus": 60},
    8: {"title": "Главный куратор хелперов", "ans_bonus": 2000, "xp_bonus": 80},
}

FACTIONS: dict[str, dict[str, Any]] = {
    "dps": {
        "name": "ГИБДД / ДПС",
        "type": "law",
        "salary": 1800,
        "npc": "Инспектор Воробьёв",
        "min_lvl": 1,
        "mission_name": "Патруль поста ДПС",
        "ranks": {
            1: "Рядовой ДПС",
            2: "Мл. сержант ДПС",
            3: "Сержант ДПС",
            4: "Ст. сержант ДПС",
            5: "Прапорщик ДПС",
            6: "Лейтенант ДПС",
            7: "Капитан ДПС",
            8: "Майор ДПС",
            9: "Подполковник ДПС",
            10: "Полковник ГИБДД",
        },
    },
    "pps": {
        "name": "УМВД / ППС",
        "type": "law",
        "salary": 1750,
        "npc": "Сержант Соколов",
        "min_lvl": 1,
        "mission_name": "Ночной рейд по району",
        "ranks": {
            1: "Рядовой полиции",
            2: "Мл. сержант полиции",
            3: "Сержант полиции",
            4: "Ст. сержант полиции",
            5: "Старшина полиции",
            6: "Лейтенант полиции",
            7: "Капитан полиции",
            8: "Майор полиции",
            9: "Подполковник полиции",
            10: "Генерал-майор УМВД",
        },
    },
    "fsb": {
        "name": "ФСБ России",
        "type": "law",
        "salary": 2400,
        "npc": "Майор Орлов",
        "min_lvl": 3,
        "mission_name": "Спецоперация «Перехват»",
        "ranks": {
            1: "Стажёр ФСБ",
            2: "Мл. оперативник",
            3: "Оперативник",
            4: "Ст. оперативник",
            5: "Следователь",
            6: "Ст. следователь",
            7: "Инспектор УСБ",
            8: "Начальник отдела",
            9: "Зам. директора ФСБ",
            10: "Директор УФСБ",
        },
    },
    "mchs": {
        "name": "МЧС России",
        "type": "gov",
        "salary": 1950,
        "npc": "Капитан Громов",
        "min_lvl": 1,
        "mission_name": "Ликвидация возгорания",
        "ranks": {
            1: "Рядовой МЧС",
            2: "Мл. сержант МЧС",
            3: "Сержант МЧС",
            4: "Старшина МЧС",
            5: "Прапорщик МЧС",
            6: "Лейтенант МЧС",
            7: "Капитан МЧС",
            8: "Майор МЧС",
            9: "Подполковник МЧС",
            10: "Генерал МЧС",
        },
    },
    "med": {
        "name": "Минздрав / Больница",
        "type": "gov",
        "salary": 2050,
        "npc": "Доктор Волкова",
        "min_lvl": 1,
        "mission_name": "Выезд на экстренный вызов",
        "ranks": {
            1: "Санитар",
            2: "Фельдшер",
            3: "Медбрат / Медсестра",
            4: "Спасатель МЗ",
            5: "Терапевт",
            6: "Травматолог",
            7: "Хирург",
            8: "Заведующий отделением",
            9: "Зам. главврача",
            10: "Главный врач",
        },
    },
    "smi": {
        "name": "ТРК «Ритм» / СМИ",
        "type": "gov",
        "salary": 1850,
        "npc": "Редактор Морозов",
        "min_lvl": 1,
        "mission_name": "Прямой эфир и репортаж",
        "ranks": {
            1: "Практикант",
            2: "Фотокорреспондент",
            3: "Журналист",
            4: "Корреспондент",
            5: "Репортёр",
            6: "Оператор",
            7: "Ведущий",
            8: "Редактор",
            9: "Главный редактор",
            10: "Директор ТРК",
        },
    },
    "vo": {
        "name": "Воинская часть / Армия",
        "type": "law",
        "salary": 2150,
        "npc": "Старшина Кузнецов",
        "min_lvl": 1,
        "mission_name": "Караул и строевая подготовка",
        "ranks": {
            1: "Рядовой",
            2: "Ефрейтор",
            3: "Мл. сержант",
            4: "Сержант",
            5: "Ст. сержант",
            6: "Старшина",
            7: "Прапорщик",
            8: "Лейтенант",
            9: "Майор",
            10: "Полковник ВЧ",
        },
    },
    "gov": {
        "name": "Правительство области",
        "type": "gov",
        "salary": 2300,
        "npc": "Советник Белов",
        "min_lvl": 2,
        "mission_name": "Проверка гособъектов",
        "ranks": {
            1: "Водитель",
            2: "Охранник",
            3: "Начальник охраны",
            4: "Секретарь",
            5: "Советник",
            6: "Лицензёр",
            7: "Адвокат",
            8: "Депутат",
            9: "Вице-губернатор",
            10: "Губернатор области",
        },
    },
    "opg_sun": {
        "name": "ОПГ «Солнцевские»",
        "type": "crime",
        "salary": 2100,
        "npc": "Авторитет Зверь",
        "min_lvl": 1,
        "mission_name": "Рэкет и контроль точек",
        "ranks": {
            1: "Пацан",
            2: "Шнырь",
            3: "Фраер",
            4: "Барыга",
            5: "Блатной",
            6: "Свояк",
            7: "Браток",
            8: "Смотрящий",
            9: "Положенец",
            10: "Вор в законе",
        },
    },
    "opg_orekh": {
        "name": "ОПГ «Ореховские»",
        "type": "crime",
        "salary": 2200,
        "npc": "Бухгалтер Лютый",
        "min_lvl": 2,
        "mission_name": "Налёт на инкассацию",
        "ranks": {
            1: "Молодой",
            2: "Бегунок",
            3: "Боец",
            4: "Торпеда",
            5: "Старший боец",
            6: "Бригадир",
            7: "Авторитет",
            8: "Смотрящий",
            9: "Правая рука",
            10: "Батя",
        },
    },
}

DEFAULT_FACTION_STATE: dict[str, dict[str, Any]] = {
    fid: {
        "treasury": 25000,
        "materials": 500,
        "rating": 0,
        "last_raid": 0.0,
        "last_bonus": 0.0,
    }
    for fid in FACTIONS
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

FOOD_ITEMS: dict[str, dict[str, Any]] = {
    "shawarma": {"name": "🌯 Шаурма у вокзала", "price": 600, "hunger": 25, "stamina": 10, "hp": 5},
    "dinner": {"name": "🍲 Обед в столовой", "price": 1400, "hunger": 55, "stamina": 25, "hp": 10},
    "energy": {"name": "⚡ Энергетик «Drive»", "price": 1100, "hunger": 5, "stamina": 45, "hp": 0},
    "rest": {"name": "🛌 Короткий отдых", "price": 0, "hunger": 0, "stamina": 25, "hp": 5},
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
faction_state: dict[str, dict[str, Any]] = {}
next_game_id: int = 100
next_ticket_id: int = 1
maintenance_mode: bool = False
maintenance_reason: str = "Проводятся технические работы. Попробуйте позже."


class SupportStates(StatesGroup):
    waiting_message = State()


def clamp_stat(val: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(val)))


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
    u["hp"] = clamp_stat(u.get("hp", 100))
    u["hunger"] = clamp_stat(u.get("hunger", 100))
    u["stamina"] = clamp_stat(u.get("stamina", 100))
    u["faction"] = str(u.get("faction") or "none")
    u["rank"] = max(1, min(10, int(u.get("rank", 1))))
    u["f_warns"] = max(0, min(3, int(u.get("f_warns", 0))))
    u["leader_of"] = u.get("leader_of") if u.get("leader_of") in FACTIONS else None
    u["admin_lvl"] = max(0, min(8, int(u.get("admin_lvl", 0))))
    u["helper_lvl"] = max(0, min(8, int(u.get("helper_lvl", 0))))
    u["helper_answers"] = max(0, int(u.get("helper_answers", 0)))
    u["faction_points"] = max(0, int(u.get("faction_points", 0)))
    u["last_fmission"] = float(u.get("last_fmission", 0.0))
    u["is_media"] = bool(u.get("is_media", False))
    u["banned"] = bool(u.get("banned", False))
    u["ban_reason"] = str(u.get("ban_reason") or "")
    u["tempban_until"] = float(u.get("tempban_until", 0.0))
    u["tempban_reason"] = str(u.get("tempban_reason") or "")
    u["wanted"] = max(0, min(6, int(u.get("wanted", 0))))
    u["fines"] = max(0, int(u.get("fines", 0)))
    u["last_work"] = float(u.get("last_work", 0.0))
    u["last_npc"] = float(u.get("last_npc", 0.0))
    u["casino_wins"] = max(0, int(u.get("casino_wins", 0)))
    u["casino_losses"] = max(0, int(u.get("casino_losses", 0)))
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


def get_admin_lvl(uid: int) -> int:
    if is_creator(uid):
        return 8
    u = users.get(str(uid))
    if not isinstance(u, dict):
        return 0
    return max(0, min(8, int(u.get("admin_lvl", 0))))


def get_admin_title(lvl: int) -> str:
    if lvl <= 0:
        return "Нет"
    info = ADMIN_RANKS.get(lvl)
    return f"{lvl} ур. ({info['title']})" if info else f"{lvl} ур."


def is_admin(uid: int, min_lvl: int = 1) -> bool:
    if is_creator(uid):
        return True
    return get_admin_lvl(uid) >= min_lvl


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


def get_helper_title(lvl: int) -> str:
    if lvl <= 0:
        return "Нет"
    info = HELPER_RANKS.get(lvl)
    return f"{lvl} ур. ({info['title']})" if info else f"{lvl} ур."


def get_faction_rank_title(fid: str, rank: int) -> str:
    fdata = FACTIONS.get(fid)
    if not fdata:
        return f"{rank} ранг"
    r_map = fdata.get("ranks") or {}
    return str(r_map.get(rank) or f"{rank} ранг")


def get_fstate(fid: str) -> dict[str, Any]:
    if fid not in faction_state:
        faction_state[fid] = dict(DEFAULT_FACTION_STATE.get(fid, {
            "treasury": 25000,
            "materials": 500,
            "rating": 0,
            "last_raid": 0.0,
            "last_bonus": 0.0,
        }))
    return faction_state[fid]


def is_police_faction(u: dict[str, Any]) -> bool:
    return str(u.get("faction") or "") in {"dps", "pps", "fsb", "vo"} or is_admin(int(u.get("tg_id", 0)), 1)


def load_state() -> None:
    global next_game_id, next_ticket_id
    users.clear()
    faction_apps.clear()
    businesses.clear()
    families.clear()
    promocodes.clear()
    support_tickets.clear()
    faction_state.clear()
    for fid, fdef in DEFAULT_FACTION_STATE.items():
        faction_state[fid] = dict(fdef)

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
    global maintenance_mode, maintenance_reason
    next_ticket_id = max(1, int(raw.get("next_ticket_id", 1)))
    maintenance_mode = bool(raw.get("maintenance_mode", False))
    maintenance_reason = str(raw.get("maintenance_reason") or "Проводятся технические работы. Попробуйте позже.")

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

    raw_fstate = raw.get("faction_state") if isinstance(raw.get("faction_state"), dict) else {}
    for fid, fsval in raw_fstate.items():
        if fid in FACTIONS and isinstance(fsval, dict):
            base_fs = dict(DEFAULT_FACTION_STATE[fid])
            base_fs.update(fsval)
            faction_state[fid] = base_fs


def save_state() -> None:
    payload = {
        "next_game_id": next_game_id,
        "next_ticket_id": next_ticket_id,
        "maintenance_mode": maintenance_mode,
        "maintenance_reason": maintenance_reason,
        "users": users,
        "faction_apps": faction_apps,
        "businesses": businesses,
        "families": families,
        "promocodes": promocodes,
        "support_tickets": support_tickets,
        "faction_state": faction_state,
    }
    tmp_file = f"{DATA_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, DATA_FILE)


def parse_duration_seconds(raw_dur: str) -> int | None:
    s = raw_dur.strip().lower()
    if not s:
        return None
    if s.isdigit():
        mins = int(s)
        return mins * 60 if mins > 0 else None
    total = 0
    matches = re.findall(r"(\d+)\s*([smhdчдмн]|сек|мин|час|дн|день|дня|дней)", s)
    if not matches:
        return None
    joined_len = sum(len(m[0]) + len(m[1]) for m in matches)
    if joined_len < len(re.sub(r"\s+", "", s)):
        return None
    for num_str, unit in matches:
        val = int(num_str)
        if val <= 0:
            return None
        if unit in {"s", "сек"}:
            total += val
        elif unit in {"m", "мин"}:
            total += val * 60
        elif unit in {"h", "ч", "час"}:
            total += val * 3600
        elif unit in {"d", "д", "дн", "день", "дня", "дней"}:
            total += val * 86400
    return total if total > 0 else None


def format_duration(seconds: float) -> str:
    sec = max(1, int(seconds))
    days, rem = divmod(sec, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} д.")
    if hours:
        parts.append(f"{hours} ч.")
    if mins:
        parts.append(f"{mins} мин.")
    if secs and not days:
        parts.append(f"{secs} сек.")
    return " ".join(parts) if parts else "меньше минуты"


class BanMiddleware:
    async def __call__(self, handler, event, data):
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id

        if uid is not None and not is_creator(uid):
            u = users.get(str(uid))
            if isinstance(u, dict):
                if u.get("banned"):
                    reason = u.get("ban_reason") or "Нарушение правил сервера"
                    text = f"🚫 Ваш аккаунт заблокирован.
Причина: {reason}"
                    if isinstance(event, Message):
                        await event.answer(text)
                    elif isinstance(event, CallbackQuery):
                        await event.answer(text, show_alert=True)
                    return
                tb_until = float(u.get("tempban_until", 0.0) or 0.0)
                if tb_until > 0:
                    now_ts = time.time()
                    if now_ts < tb_until:
                        rem_txt = format_duration(tb_until - now_ts)
                        tb_reason = u.get("tempban_reason") or "Нарушение правил сервера"
                        text = f"⏳ Ваш аккаунт временно заблокирован.
Осталось: **{rem_txt}**
Причина: {tb_reason}"
                        if isinstance(event, Message):
                            await safe_answer(event, text, parse_mode="Markdown")
                        elif isinstance(event, CallbackQuery):
                            await event.answer(f"⏳ Временный бан ({rem_txt}). Причина: {tb_reason}", show_alert=True)
                        return
                    else:
                        u["tempban_until"] = 0.0
                        u["tempban_reason"] = ""
                        save_state()
        if uid is not None and maintenance_mode and not is_admin(uid, 1):
            m_text = f"🛠 **Технические работы**
{maintenance_reason}"
            if isinstance(event, Message):
                await safe_answer(event, m_text, parse_mode="Markdown")
            elif isinstance(event, CallbackQuery):
                await event.answer(f"🛠 Технические работы: {maintenance_reason}", show_alert=True)
            return
        return await handler(event, data)


def main_kb(uid: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💵 Работа")],
        [KeyboardButton(text="🍔 Еда и отдых"), KeyboardButton(text="🏥 Больница")],
        [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="🏛 Фракции")],
        [KeyboardButton(text="🏢 Бизнесы"), KeyboardButton(text="🏠 Недвижимость")],
        [KeyboardButton(text="🚗 Автосалон"), KeyboardButton(text="👨‍👩‍👧‍👦 Семья")],
        [KeyboardButton(text="🏆 Топ-10"), KeyboardButton(text="🎫 Поддержка")],
        [KeyboardButton(text="📖 Команды")],
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
    await safe_answer(
        message,
        f"🇷🇺 Добро пожаловать в **Criminal Russia RP**!
"
        f"Имя: **{p['name']}** | Игровой ID: **`#{p['game_id']}`**
"
        f"Наличные: **{p['money']} ₽** | Банк: **{p['bank']} ₽** | Уровень: **{p['lvl']}**
"
        f"❤️ HP: `{p['hp']}/100` | 🍗 Голод: `{p['hunger']}/100` | ⚡ Выносливость: `{p['stamina']}/100`",
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
        "• `/work` — отработать смену (тратит выносливость и голод)",
        "• `/casino <сумма>` — сыграть в казино",
        "• `/heal` — пройти лечение в больнице",
        "• `/promo <КОД>` — активировать промокод",
        "• `/support <текст>` — написать в поддержку (или кнопка «🎫 Поддержка»)",
        "• `/members [фракция]` — состав фракции",
        "• `/r <текст>`, `/fapps`, `/faccept`, `/fdecline`, `/fdeposit`, `/fwarn` — фракции",
        "",
        "🚓 **ДПС / ППС / ФСБ / ВЧ:**",
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
            "🛡 **Администрация (ранги 1–8):**",
            "• `/admins` — список администрации и ранги 1–8",
            "• `/players` — список игроков",
            "• `/addpromo <КОД> <сумма> <xp> <активаций>` — создать промокод",
            "• `/delpromo <КОД>` — удалить промокод",
            "• `/sethelper <ID> <0..8>` и `/helpers` — ранги хелперов (1–8)",
            "• `/setmedia <ID> <0|1>` — выдать роль медиа",
            "• `/setadmin <ID> <0..8>` — выдать уровень админа",
            "• `/setleader <ID> <фракция|none>` — назначить лидера",
            "• `/ban <ID> [причина]` и `/unban <ID>`",
            "• `/tempban <ID> <срок> [причина]` и `/untempban <ID>`",
            "• `/resetplayer <ID>` и `/wipeall CONFIRM`",
        ])
    await safe_answer(message, "
".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")


@dp.message(F.text == "👤 Профиль")
async def btn_profile(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fac_key = p.get("faction", "none")
    if fac_key in FACTIONS:
        fac_name = FACTIONS[fac_key]["name"]
        rk_title = get_faction_rank_title(fac_key, int(p["rank"]))
        warns_txt = f" | Выговоров: `{p.get('f_warns', 0)}/3`" if int(p.get("f_warns", 0)) > 0 else ""
        fac_line = f"🏛 Фракция: **{fac_name}** — **{rk_title}** (`{p['rank']}/10`, очки: `{p['faction_points']}`{warns_txt})"
    else:
        fac_line = "🏛 Фракция: **Гражданский**"
    role_tag = " 👑 Лидер" if p.get("leader_of") else ""
    a_lvl = get_admin_lvl(uid)
    admin_line = f"
🛡 Администрация: **{get_admin_title(a_lvl)}**" if is_creator(uid) or a_lvl > 0 else ""
    h_lvl = int(p.get("helper_lvl", 0))
    helper_line = f"
🛟 Хелперка: **{get_helper_title(h_lvl)}** (ответов: `{p['helper_answers']}`)" if h_lvl > 0 else ""
    cars_txt = ", ".join(SHOP_CARS[c]["name"] for c in p["cars"] if c in SHOP_CARS) or "Нет"
    houses_txt = ", ".join(SHOP_HOUSES[h]["name"] for h in p["houses"] if h in SHOP_HOUSES) or "Нет"

    await safe_answer(
        message,
        f"👤 **Профиль: {p['name']}** (`#{p['game_id']}`)
"
        f"⭐ Уровень: **{p['lvl']}** (опыт: `{p['xp']}`)
"
        f"💵 Наличные: **{p['money']} ₽** | 🏦 Банк: **{p['bank']} ₽**
"
        f"❤️ Здоровье: **`{p['hp']}/100`** | 🍗 Голод: **`{p['hunger']}/100`** | ⚡ Выносливость: **`{p['stamina']}/100`**
"
        f"🎰 Казино: побед **`{p['casino_wins']}`** / поражений **`{p['casino_losses']}`**
"
        f"🚨 Розыск: **`{p['wanted']}/6`** | 🧾 Штрафы: **{p['fines']} ₽**
"
        f"{fac_line}{role_tag}{admin_line}{helper_line}
"
        f"🚗 Авто: {cars_txt}
"
        f"🏠 Недвижимость: {houses_txt}",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("work"))
@dp.message(F.text == "💵 Работа")
async def cmd_work(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)

    if int(p.get("hp", 100)) <= 10:
        await safe_answer(message, "🏥 Вы слишком ослабли для работы! Загляните в **«🏥 Больница»** (`/heal`).", parse_mode="Markdown")
        return
    if int(p.get("hunger", 100)) < 15:
        await safe_answer(message, "🍗 Вы слишком голодны для смены (голод `< 15`). Перекусите в **«🍔 Еда и отдых»**.", parse_mode="Markdown")
        return
    if int(p.get("stamina", 100)) < 20:
        await safe_answer(message, "⚡ Не хватает выносливости (нужно минимум `20`). Восстановите силы в **«🍔 Еда и отдых»**.", parse_mode="Markdown")
        return

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
    house_bonus = sum(SHOP_HOUSES[h]["bonus_bank"] for h in p["houses"] if h in SHOP_HOUSES)
    reward = base + car_bonus + house_bonus + random.randint(100, 400)

    stamina_cost = 24 if int(p["hunger"]) < 35 else 16
    hunger_cost = random.randint(8, 15)

    p["money"] += reward
    p["xp"] += 25
    p["stamina"] = clamp_stat(int(p["stamina"]) - stamina_cost)
    p["hunger"] = clamp_stat(int(p["hunger"]) - hunger_cost)
    p["last_work"] = now
    if p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()

    await safe_answer(
        message,
        f"💼 Смена завершена! Вы заработали **+{reward} ₽** и **+25 XP**.
"
        f"Наличные: **{p['money']} ₽** | Уровень: **{p['lvl']}**
"
        f"🍗 Голод: **`{p['hunger']}/100`** | ⚡ Выносливость: **`{p['stamina']}/100`**",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


# --- ЕДА, ВЫНОСЛИВОСТЬ И БОЛЬНИЦА ---

def render_food_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌯 Шаурма (600 ₽ | +25 голод, +10 сил)", callback_data="eat:shawarma")],
            [InlineKeyboardButton(text="🍲 Обед (1 400 ₽ | +55 голод, +25 сил)", callback_data="eat:dinner")],
            [InlineKeyboardButton(text="⚡ Энергетик (1 100 ₽ | +45 сил)", callback_data="eat:energy")],
            [InlineKeyboardButton(text="🛌 Отдохнуть (0 ₽ | +25 сил, +5 HP)", callback_data="eat:rest")],
        ]
    )


@dp.message(F.text == "🍔 Еда и отдых")
async def btn_food(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await safe_answer(
        message,
        f"🍔 **Питание и восстановление сил**
"
        f"❤️ HP: **`{p['hp']}/100`** | 🍗 Голод: **`{p['hunger']}/100`** | ⚡ Выносливость: **`{p['stamina']}/100`**
"
        f"Наличные: **{p['money']} ₽**",
        reply_markup=render_food_kb(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("eat:"))
async def cb_eat(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    key = callback.data.split(":", 1)[1]
    item = FOOD_ITEMS.get(key)
    if not item:
        await callback.answer("Неизвестный вариант", show_alert=True)
        return
    price = int(item["price"])
    if price > 0 and int(p["money"]) < price:
        await callback.answer(f"Не хватает наличных (нужно {price} ₽)", show_alert=True)
        return

    p["money"] -= price
    p["hunger"] = clamp_stat(int(p["hunger"]) + int(item["hunger"]))
    p["stamina"] = clamp_stat(int(p["stamina"]) + int(item["stamina"]))
    p["hp"] = clamp_stat(int(p["hp"]) + int(item["hp"]))
    save_state()

    await callback.answer(
        f"{item['name']}: голод {p['hunger']}/100, силы {p['stamina']}/100",
        show_alert=True,
    )
    if callback.message:
        await callback.message.answer(
            f"✅ Вы воспользовались пунктом **«{item['name']}»** (-{price} ₽).
"
            f"❤️ HP: **`{p['hp']}/100`** | 🍗 Голод: **`{p['hunger']}/100`** | ⚡ Выносливость: **`{p['stamina']}/100`**",
            parse_mode="Markdown",
        )


def render_hospital_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🩺 Стандартное лечение (1 500 ₽ -> 100 HP)", callback_data="hosp:std")],
            [InlineKeyboardButton(text="💉 Полный курс + питание (3 000 ₽ -> 100/100/100)", callback_data="hosp:full")],
        ]
    )


async def perform_hospital_treatment(uid: int, full_name: str, mode: str) -> tuple[bool, str]:
    p = get_player(uid, full_name)
    cost = 3000 if mode == "full" else 1500
    if mode == "std" and int(p["hp"]) >= 100:
        return False, "У вас уже максимальное здоровье (100/100 HP)."
    if int(p["money"]) < cost:
        return False, f"Недостаточно наличных на лечение (нужно **{cost} ₽**)."

    p["money"] -= cost
    p["hp"] = 100
    if mode == "full":
        p["hunger"] = 100
        p["stamina"] = 100
    else:
        p["stamina"] = clamp_stat(int(p["stamina"]) + 30)

    med_fs = get_fstate("med")
    med_fs["treasury"] = int(med_fs.get("treasury", 0)) + int(cost * 0.4)
    save_state()

    if mode == "full":
        return True, f"💉 Полный курс лечения пройден (-{cost} ₽)! Восстановлены **100 HP**, **100 голода** и **100 выносливости**."
    return True, f"🩺 Лечение успешно завершено (-{cost} ₽)! Здоровье восстановлено до **100 HP**."


@dp.message(Command("heal"))
@dp.message(F.text == "🏥 Больница")
async def cmd_hospital(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await safe_answer(
        message,
        f"🏥 **Областная больница (Минздрав)**
"
        f"Ваше здоровье: **`{p['hp']}/100 HP`** | Голод: **`{p['hunger']}/100`** | Выносливость: **`{p['stamina']}/100`**
"
        f"Наличные: **{p['money']} ₽**

"
        f"Выберите курс лечения или используйте `/heal`:",
        reply_markup=render_hospital_kb(),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.startswith("hosp:"))
async def cb_hospital(callback: CallbackQuery):
    mode = callback.data.split(":", 1)[1]
    ok, msg_txt = await perform_hospital_treatment(callback.from_user.id, callback.from_user.full_name, mode)
    await callback.answer(msg_txt, show_alert=True)
    if ok and callback.message:
        await callback.message.answer(msg_txt, parse_mode="Markdown")


# --- КАЗИНО ---

def render_casino_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎲 5 000 ₽", callback_data="cas:std:5000"),
                InlineKeyboardButton(text="🎲 25 000 ₽", callback_data="cas:std:25000"),
                InlineKeyboardButton(text="🎲 100 000 ₽", callback_data="cas:std:100000"),
            ],
            [
                InlineKeyboardButton(text="🔥 Риск x5 (10 000 ₽)", callback_data="cas:risk:10000"),
                InlineKeyboardButton(text="🔥 Риск x5 (50 000 ₽)", callback_data="cas:risk:50000"),
            ],
        ]
    )


def run_casino_round(p: dict[str, Any], bet: int, mode: str = "std") -> tuple[bool, str]:
    if bet < 100:
        return False, "🎰 Минимальная ставка в казино — **100 ₽**."
    if bet > 10_000_000:
        return False, "🎰 Максимальная ставка за один раунд — **10 000 000 ₽**."
    if int(p["money"]) < bet:
        return False, f"💸 Недостаточно наличных! У вас **{p['money']} ₽**."

    roll = random.randint(1, 100)
    if mode == "risk":
        if roll >= 82:
            payout = bet * 5
            profit = payout - bet
            p["money"] += profit
            p["casino_wins"] = int(p.get("casino_wins", 0)) + 1
            save_state()
            return True, f"🔥 **РИСК-ДЖЕКПОТ (`{roll}/100`)!** Выигрыш **{payout} ₽** (чистыми **+{profit} ₽**). Баланс: **{p['money']} ₽**."
        p["money"] -= bet
        p["casino_losses"] = int(p.get("casino_losses", 0)) + 1
        save_state()
        return True, f"📉 Не повезло в риск-игре (`{roll}/100`). Потеряно **-{bet} ₽**. Баланс: **{p['money']} ₽**."

    if roll >= 92:
        payout = int(bet * 3.5)
        profit = payout - bet
        p["money"] += profit
        p["casino_wins"] = int(p.get("casino_wins", 0)) + 1
        save_state()
        return True, f"💎 **КРУПНЫЙ ВЫИГРЫШ (`{roll}/100`, x3.5)!** Выплата **{payout} ₽** (чистыми **+{profit} ₽**). Баланс: **{p['money']} ₽**."
    if roll >= 53:
        payout = int(bet * 2.0)
        profit = payout - bet
        p["money"] += profit
        p["casino_wins"] = int(p.get("casino_wins", 0)) + 1
        save_state()
        return True, f"🎲 **ПОБЕДА (`{roll}/100`, x2.0)!** Выплата **{payout} ₽** (чистыми **+{profit} ₽**). Баланс: **{p['money']} ₽**."

    p["money"] -= bet
    p["casino_losses"] = int(p.get("casino_losses", 0)) + 1
    save_state()
    return True, f"📉 Проигрыш (`{roll}/100`). Ставка **{bet} ₽** сгорела. Баланс: **{p['money']} ₽**."


@dp.message(F.text == "🎰 Казино")
async def btn_casino(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await safe_answer(
        message,
        f"🎰 **Казино «Imperial»**
"
        f"Наличные: **{p['money']} ₽** | Побед: `{p['casino_wins']}` / Поражений: `{p['casino_losses']}`

"
        f"• **Обычная игра**: шанс победы ~48% (x2.0 / x3.5)
"
        f"• **Риск x5**: шанс победы ~19% (x5.0)
"
        f"Выберите кнопку или введите `/casino <сумма>`:",
        reply_markup=render_casino_kb(),
        parse_mode="Markdown",
    )


@dp.message(Command("casino"))
async def cmd_casino(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: `/casino <сумма>` (например, `/casino 10000`)", parse_mode="Markdown")
        return
    _, text = run_casino_round(p, int(parts[1]), mode="std")
    await safe_answer(message, text, parse_mode="Markdown")


@dp.callback_query(F.data.startswith("cas:"))
async def cb_casino(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    _, mode, amt_s = callback.data.split(":", 2)
    _, text = run_casino_round(p, int(amt_s), mode=mode)
    await callback.answer("Ставка сыграна!")
    if callback.message:
        await callback.message.answer(text, parse_mode="Markdown")


# --- ПРОМОКОДЫ ---

@dp.message(Command("addpromo"))
async def cmd_addpromo(message: Message):
    uid = message.from_user.id
    if not (is_admin(uid, 3) or is_media(uid)):
        await safe_answer(message, "⛔ Создавать промокоды можно с 3 ранга администратора или с ролью медиа.")
        return

    parts = (message.text or "").split()
    if len(parts) not in (4, 5):
        await safe_answer(
            message,
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
    await safe_answer(
        message,
        f"🎟 Промокод **`{code}`** создан!
"
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

    await safe_answer(
        message,
        f"🎉 Промокод **`{code}`** активирован!
"
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
            roster.append((r_val, str(u.get("name", "Игрок")), int(u.get("game_id", 0)), int(u.get("wanted", 0)), int(u.get("f_warns", 0))))

    roster.sort(key=lambda item: (-item[0], item[1].lower()))
    fac_name = FACTIONS[fid]["name"]

    if not roster:
        await safe_answer(message, f"👥 В фракции **{fac_name}** сейчас никого нет.", parse_mode="Markdown")
        return

    lines = [f"👥 **Состав фракции «{fac_name}»** (`{len(roster)}` чел.):
"]
    for idx, (r_val, uname, gid, w_lvl, fw) in enumerate(roster, start=1):
        leader_tag = " 👑 Лидер" if r_val == 10 else ""
        wanted_tag = f" 🚨`{w_lvl}`" if w_lvl > 0 else ""
        warn_tag = f" ⚠️`{fw}/3`" if fw > 0 else ""
        lines.append(f"{idx}. **{uname}** (`#{gid}`) — ранг `{r_val}/10`{leader_tag}{wanted_tag}{warn_tag}")

    await safe_answer(message, "
".join(lines), parse_mode="Markdown")


# --- ДПС / ППС / ФСБ / ВЧ: РОЗЫСК И ШТРАФЫ ---

@dp.message(Command("wanted"))
async def cmd_wanted(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Команда доступна сотрудникам ДПС / ППС / ФСБ / ВЧ и администрации.")
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
    await safe_answer(
        message,
        f"🚨 Игроку **{target['name']}** (`#{target_gid}`) выдан розыск: **`{stars}/6`**.",
        parse_mode="Markdown",
    )


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Команда доступна сотрудникам ДПС / ППС / ФСБ / ВЧ и администрации.")
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
        await safe_answer(message, "⛔ Выписывать штрафы могут сотрудники ДПС / ППС / ФСБ / ВЧ и администрация.")
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

    await safe_answer(
        message,
        f"🧾 Выписан штраф игроку **{target['name']}** (`#{target_gid}`) на **{amount} ₽** ({paid_msg}).
"
        f"Причина: _{reason}_",
        parse_mode="Markdown",
    )


# --- БИЗНЕСЫ ---

@dp.message(F.text == "🏢 Бизнесы")
async def btn_biz(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    await render_biz_menu(message, uid, edit=False)


async def render_biz_menu(target_msg: Message, uid: int, edit: bool = False):
    now = time.time()
    lines = ["🏢 **Бизнесы Criminal Russia:**
"]
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
    text = "
".join(lines)
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
    await safe_answer(
        message,
        "🎫 **Служба поддержки**
"
        "Напишите ваш вопрос или описание проблемы одним сообщением — хелперы или администраторы ответят вам.
"
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

    await safe_answer(
        message,
        f"✅ Обращение **`#{tid}`** отправлено в поддержку! Ожидайте ответа.",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )
    await notify_staff_ticket(
        bot,
        tid,
        f"🎫 **Новый тикет `#{tid}`**
"
        f"Игрок: **{p['name']}** (`#{p['game_id']}`, TG: `{uid}`)
"
        f"Текст: {body}
"
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

    lines = [f"🛟 **Открытые тикеты** (`{len(open_list)}`):
"]
    for t in open_list[:20]:
        msgs = t.get("messages") or []
        last_txt = msgs[-1].get("text", "") if msgs else ""
        lines.append(
            f"• Тикет **`#{t['id']}`** — **{t.get('user_name')}** (`#{t.get('game_id')}`)
"
            f"  _{last_txt[:100]}_"
        )
    st = get_player(uid, message.from_user.full_name)
    lines.append(f"
Ваш ранг: **{get_helper_title(int(st.get('helper_lvl', 0)))}** | Ответов: `{st.get('helper_answers', 0)}`")
    lines.append("Команды: `/answer <ID> <текст>` | `/closeticket <ID>` | `/helpers`")
    await safe_answer(message, "
".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")


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
    h_lvl = int(staff.get("helper_lvl", 0))
    h_info = HELPER_RANKS.get(h_lvl, {"title": "Администрация", "ans_bonus": 300, "xp_bonus": 15})
    bonus_money = int(h_info["ans_bonus"])
    bonus_xp = int(h_info["xp_bonus"])

    staff["helper_answers"] = int(staff.get("helper_answers", 0)) + 1
    staff["money"] = int(staff.get("money", 0)) + bonus_money
    staff["xp"] = int(staff.get("xp", 0)) + bonus_xp
    while staff["xp"] >= staff["lvl"] * 100:
        staff["xp"] -= staff["lvl"] * 100
        staff["lvl"] += 1

    promo_note = ""
    if 1 <= h_lvl < 6:
        thresholds = {1: 5, 2: 15, 3: 30, 4: 55, 5: 90}
        if staff["helper_answers"] >= thresholds.get(h_lvl, 9999):
            staff["helper_lvl"] = h_lvl + 1
            promo_note = f"
🎉 Поздравляем! Вы повышены до ранга **{get_helper_title(h_lvl + 1)}**!"

    ticket.setdefault("messages", []).append({
        "from": "staff",
        "name": f"{staff['name']} [{h_info['title']}]",
        "text": reply_text,
    })
    save_state()

    target_uid = int(ticket["user_id"])
    try:
        await safe_send(
            bot,
            target_uid,
            f"💬 **Ответ поддержки по тикету `#{tid}`** ({staff['name']}):
{reply_text}",
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await safe_answer(
        message,
        f"✅ Ответ по тикету `#{tid}` отправлен! Награда хелпера: **+{bonus_money} ₽**, **+{bonus_xp} XP**.{promo_note}",
        parse_mode="Markdown",
    )


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
        await safe_send(
            bot,
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
    body = f"{header}

{parts[1].strip()}"
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
    lines = [f"📋 **Игроки** (всего: `{len(items)}`):
"]
    for u in items[:40]:
        has_tb = float(u.get("tempban_until", 0.0) or 0.0) > time.time()
        ban_tag = " 🚫" if u.get("banned") else (" ⏳" if has_tb else "")
        lines.append(
            f"• **`#{u['game_id']}`** {u['name']} — {u['lvl']} ур. | {u['money'] + u['bank']} ₽{ban_tag}"
        )
    await safe_answer(message, "
".join(lines), parse_mode="Markdown")


@dp.message(Command("admins"))
async def cmd_admins(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 1):
        await safe_answer(message, "⛔ Список администрации доступен с 1 ранга администратора.")
        return
    staff = []
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            normalize_player(u, tg_id)
            al = get_admin_lvl(tg_id)
            if is_creator(tg_id) or al > 0:
                staff.append((al, is_creator(tg_id), str(u["name"]), int(u["game_id"])))
    staff.sort(key=lambda x: (-x[0], not x[1], x[2].lower()))
    ranks_list = "
".join(f"• `{k}` — **{v['title']}** ({v['perm_desc']})" for k, v in ADMIN_RANKS.items())
    lines = ["🛡 **Иерархия администрации (1–8):**
" + ranks_list + "

📋 **Текущий состав:**"]
    if not staff:
        lines.append("Администраторов пока нет.")
    else:
        for idx, (al, cr, nm, gid) in enumerate(staff, start=1):
            tag = " 👑 Создатель" if cr else ""
            lines.append(f"{idx}. **{nm}** (`#{gid}`) — **{get_admin_title(al)}**{tag}")
    await safe_answer(message, "
".join(lines), parse_mode="Markdown")


@dp.message(Command("sethelper"))
async def cmd_sethelper(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    can_manage = is_admin(uid, 4) or int(actor.get("helper_lvl", 0)) >= 7
    if not can_manage:
        await safe_answer(message, "⛔ Назначать хелперов могут админы 4+ ранга или кураторы хелперов (7–8 ранг).")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        ranks_preview = "
".join(f"• `{k}` — {v['title']} (+{v['ans_bonus']} ₽ за ответ)" for k, v in HELPER_RANKS.items())
        await safe_answer(
            message,
            f"Формат: `/sethelper <игровой_ID> <0..8>`

**Иерархия хелперов:**
{ranks_preview}",
            parse_mode="Markdown",
        )
        return
    try:
        gid = int(parts[1])
        lvl = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень должны быть числами.")
        return
    if not (0 <= lvl <= 8):
        await safe_answer(message, "Уровень хелпера должен быть от 0 до 8.")
        return
    if not is_admin(uid, 4) and lvl >= int(actor.get("helper_lvl", 0)):
        await safe_answer(message, "⛔ Вы не можете выдать ранг хелпера равный или выше своего.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["helper_lvl"] = lvl
    save_state()
    title_str = get_helper_title(lvl)
    await safe_answer(
        message,
        f"🛟 Игроку **{target['name']}** (`#{gid}`) установлен ранг хелпера: **{title_str}**.",
        parse_mode="Markdown",
    )
    if lvl > 0:
        await safe_send(bot, int(target["tg_id"]), f"🛟 Вам назначен ранг хелпера: **{title_str}**!", parse_mode="Markdown")


@dp.message(Command("helpers"))
async def cmd_helpers(message: Message):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Список хелперов доступен составу поддержки и администрации.")
        return
    staff_list = []
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            normalize_player(u, tg_id)
            hl = int(u.get("helper_lvl", 0))
            if hl > 0:
                staff_list.append((hl, int(u.get("helper_answers", 0)), str(u["name"]), int(u["game_id"])))
    staff_list.sort(key=lambda x: (-x[0], -x[1]))
    if not staff_list:
        await safe_answer(message, "🛟 Активных хелперов пока нет.")
        return
    lines = [f"🛟 **Состав хелперов** (`{len(staff_list)}` чел.):
"]
    for idx, (hl, ans_cnt, name, gid) in enumerate(staff_list, start=1):
        lines.append(f"{idx}. **{name}** (`#{gid}`) — **{get_helper_title(hl)}** | ответов: `{ans_cnt}`")
    await safe_answer(message, "
".join(lines), parse_mode="Markdown")


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
async def cmd_setadmin(message: Message, bot: Bot):
    uid = message.from_user.id
    actor_lvl = get_admin_lvl(uid)
    if not (is_creator(uid) or actor_lvl >= 5):
        await safe_answer(message, "⛔ Назначать администраторов можно с 5 ранга администратора или создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        ranks_preview = "
".join(f"• `{k}` — **{v['title']}**" for k, v in ADMIN_RANKS.items())
        await safe_answer(
            message,
            f"Формат: `/setadmin <игровой_ID> <0..8>`

**Ранги администрации:**
{ranks_preview}",
            parse_mode="Markdown",
        )
        return
    try:
        gid = int(parts[1])
        lvl = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень должны быть числами.")
        return
    if not (0 <= lvl <= 8):
        await safe_answer(message, "Уровень администратора должен быть от 0 до 8.")
        return
    if not is_creator(uid) and lvl >= actor_lvl:
        await safe_answer(message, f"⛔ Вы не можете выдать ранг администратора `>= {actor_lvl}` (ваш ранг: `{actor_lvl}`).")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target_tg_id = int(target["tg_id"])
    if is_creator(target_tg_id):
        await safe_answer(message, "⛔ Нельзя изменять права создателя проекта.")
        return
    if not is_creator(uid) and int(target.get("admin_lvl", 0)) >= actor_lvl:
        await safe_answer(message, "⛔ Вы не можете менять ранг администратора равного или выше вашего.")
        return
    target["admin_lvl"] = lvl
    save_state()
    title_str = get_admin_title(lvl)
    await safe_answer(
        message,
        f"🛡 Игроку **{target['name']}** (`#{gid}`) установлен уровень администратора: **{title_str}**.",
        parse_mode="Markdown",
    )
    if lvl > 0:
        await safe_send(bot, target_tg_id, f"🛡 Вам назначен уровень администратора: **{title_str}**!", parse_mode="Markdown")


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
    target["tempban_until"] = 0.0
    target["tempban_reason"] = ""
    save_state()
    await safe_answer(message, f"✅ Игрок **{target['name']}** (`#{gid}`) разблокирован (сняты постоянный и временный баны).", parse_mode="Markdown")


@dp.message(Command("tempban"))
async def cmd_tempban(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Выдавать временные баны можно со 2 ранга администратора.")
        return

    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        await safe_answer(
            message,
            "Формат: `/tempban <игровой_ID> <срок> [причина]`
"
            "Примеры срока: `30m`, `2h`, `1d`, `1d12h`, `45` (минуты)",
            parse_mode="Markdown",
        )
        return

    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return

    dur_sec = parse_duration_seconds(parts[2])
    if not dur_sec or dur_sec > 365 * 86400:
        await safe_answer(
            message,
            "Некорректный срок. Используйте формат вроде `15m`, `3h`, `2d` (до 365 дней).",
            parse_mode="Markdown",
        )
        return

    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return

    target_tg_id = int(target["tg_id"])
    if is_creator(target_tg_id):
        await safe_answer(message, "Нельзя временно заблокировать создателя.")
        return

    reason = parts[3].strip() if len(parts) == 4 and parts[3].strip() else "Нарушение правил сервера"
    until_ts = time.time() + dur_sec
    target["tempban_until"] = until_ts
    target["tempban_reason"] = reason
    save_state()

    dur_txt = format_duration(dur_sec)
    await safe_answer(
        message,
        f"⏳ Игрок **{target['name']}** (`#{gid}`) временно заблокирован на **{dur_txt}**.
"
        f"Причина: _{reason}_",
        parse_mode="Markdown",
    )
    await safe_send(
        bot,
        target_tg_id,
        f"⏳ Вы получили временный бан на **{dur_txt}**.
Причина: {reason}",
        parse_mode="Markdown",
    )


@dp.message(Command("untempban"))
async def cmd_untempban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Снимать временные баны можно со 2 ранга администратора.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/untempban <игровой_ID>`", parse_mode="Markdown")
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

    target["tempban_until"] = 0.0
    target["tempban_reason"] = ""
    save_state()
    await safe_answer(message, f"✅ Временный бан с игрока **{target['name']}** (`#{gid}`) снят.", parse_mode="Markdown")


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
    lines = ["🏠 **Недвижимость Criminal Russia:**
"]
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
    text = "
".join(lines)
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
    lines = ["🚗 **Автосалон Criminal Russia:**
"]
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
    text = "
".join(lines)
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
        await safe_answer(
            message,
            "👨‍👩‍👧‍👦 **Семьи**
"
            "Вы пока не состоите в семье.
"
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
    await safe_answer(
        message,
        f"👨‍👩‍👧‍👦 **Семья «{fdata.get('name', fid)}»** (`#{fid}`)
"
        f"👑 Глава: **{owner_name}** | Участников: **`{len(members)}`**
"
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

    if cur_fac in FACTIONS:
        fdata = FACTIONS[cur_fac]
        fs = get_fstate(cur_fac)
        rk = int(p.get("rank", 1))
        rk_title = get_faction_rank_title(cur_fac, rk)
        pending_apps = sum(
            1 for a in faction_apps.values()
            if isinstance(a, dict) and a.get("faction") == cur_fac and a.get("status") == "pending"
        )
        rows = [
            [
                InlineKeyboardButton(text=f"🎯 {fdata['mission_name']}", callback_data=f"fac_mission:{cur_fac}"),
                InlineKeyboardButton(text="💰 Получить зарплату", callback_data=f"fac_salary:{cur_fac}"),
            ],
            [
                InlineKeyboardButton(text="📦 Пополнить склад (+50 мат.)", callback_data=f"fac_mats:{cur_fac}"),
                InlineKeyboardButton(text="⚔️ Рейд / Спецоперация", callback_data=f"fac_raid:{cur_fac}"),
            ],
            [
                InlineKeyboardButton(text="👥 Состав фракции", callback_data=f"fac_roster:{cur_fac}"),
                InlineKeyboardButton(text="🏆 Рейтинг фракций", callback_data="fac_top"),
            ],
        ]
        if rk >= 8 or p.get("leader_of") == cur_fac or is_admin(uid, 3):
            rows.append([
                InlineKeyboardButton(text=f"📋 Заявки ({pending_apps})", callback_data=f"fac_apps:{cur_fac}"),
                InlineKeyboardButton(text="💸 Премия составу (10 000 ₽)", callback_data=f"fac_bonus:{cur_fac}"),
            ])
        rows.append([
            InlineKeyboardButton(text="🚪 Уволиться ПСЖ", callback_data="fac_leave_self"),
        ])
        text = (
            f"🏛 **Фракция: {fdata['name']}**
"
            f"🎖 Ваша должность: **{rk_title}** (`{rk}/10` ранг) | Выговоров: `{p.get('f_warns', 0)}/3`
"
            f"⭐ Очки службы: **`{p['faction_points']}`** | Базовый оклад: `{fdata['salary']} ₽`
"
            f"🏦 Казна фракции: **{fs['treasury']} ₽** | 📦 Склад материалов: **`{fs['materials']}` ед.**
"
            f"🔥 Рейтинг влияния: **`{fs['rating']}`**

"
            f"Команды: `/r <текст>`, `/fdeposit <сумма>`, `/members`, `/fapps`, `/fwarn <ID> [причина]`"
        )
        await safe_answer(message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
        return

    lines = [
        "🏛 **Фракции Criminal Russia RP** (вы сейчас **Гражданский**)
"
        "Выберите организацию для подачи заявки или подработки у NPC:
"
    ]
    rows = []
    for fid, fdata in FACTIONS.items():
        fs = get_fstate(fid)
        lines.append(
            f"• **{fdata['name']}** (`{fid}`) — от `{fdata['min_lvl']}` ур., оклад `{fdata['salary']} ₽`, "
            f"рейтинг `{fs['rating']}`, NPC: *{fdata['npc']}*"
        )
        rows.append([
            InlineKeyboardButton(text=f"📝 Вступить в {fdata['name']}", callback_data=f"fac_apply:{fid}"),
            InlineKeyboardButton(text=f"🤖 Задание ({fid})", callback_data=f"fac_npc:{fid}"),
        ])
    rows.append([InlineKeyboardButton(text="🏆 Рейтинг всех фракций", callback_data="fac_top")])
    await safe_answer(message, "
".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")


@dp.callback_query(F.data == "fac_top")
async def cb_fac_top(callback: CallbackQuery):
    ranking = []
    for fid, fdata in FACTIONS.items():
        fs = get_fstate(fid)
        cnt = sum(1 for u in users.values() if isinstance(u, dict) and u.get("faction") == fid)
        ranking.append((int(fs.get("rating", 0)), int(fs.get("treasury", 0)), cnt, fdata["name"]))
    ranking.sort(key=lambda x: (-x[0], -x[1]))
    lines = ["🏆 **Рейтинг влияния фракций:**
"]
    for i, (rt, tr, cnt, fname) in enumerate(ranking, start=1):
        lines.append(f"{i}. **{fname}** — 🔥 `{rt}` очков | 🏦 `{tr} ₽` | 👥 `{cnt}` чел.")
    if callback.message:
        await safe_answer(callback.message, "
".join(lines), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("fac_roster:"))
async def cb_fac_roster(callback: CallbackQuery):
    fid = callback.data.split(":", 1)[1]
    if fid not in FACTIONS:
        await callback.answer("Фракция не найдена", show_alert=True)
        return
    roster = []
    for k, u in users.items():
        if isinstance(u, dict) and u.get("faction") == fid:
            r_val = 10 if u.get("leader_of") == fid else int(u.get("rank", 1))
            roster.append((r_val, str(u.get("name", "Игрок")), int(u.get("game_id", 0))))
    roster.sort(key=lambda x: (-x[0], x[1].lower()))
    lines = [f"👥 **Состав «{FACTIONS[fid]['name']}»** (`{len(roster)}`):
"]
    for idx, (rv, nm, gid) in enumerate(roster[:25], start=1):
        lines.append(f"{idx}. **{nm}** (`#{gid}`) — {get_faction_rank_title(fid, rv)} (`{rv}/10`)")
    if callback.message:
        await safe_answer(callback.message, "
".join(lines), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("fac_apply:"))
async def cb_fac_apply(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = FACTIONS.get(fid)
    if not fdata:
        await callback.answer("Фракция не найдена", show_alert=True)
        return
    if p.get("faction") == fid:
        await callback.answer("Вы уже состоите в этой фракции", show_alert=True)
        return
    if int(p.get("lvl", 1)) < int(fdata.get("min_lvl", 1)):
        await callback.answer(f"Для вступления нужен {fdata['min_lvl']} уровень!", show_alert=True)
        return
    if fdata.get("type") == "law" and int(p.get("wanted", 0)) > 0:
        await callback.answer("Нельзя вступить в госструктуру с активным розыском!", show_alert=True)
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

    for k, u in users.items():
        if isinstance(u, dict) and u.get("faction") == fid:
            if u.get("leader_of") == fid or int(u.get("rank", 1)) >= 8:
                await safe_send(
                    bot,
                    int(k),
                    f"📩 Новая заявка в **{fdata['name']}** от **{p['name']}** (`#{p['game_id']}`, {p['lvl']} ур.)!
"
                    f"Принять: `/faccept {p['game_id']}` | Отклонить: `/fdecline {p['game_id']}`",
                    parse_mode="Markdown",
                )

    await callback.answer(f"Заявка в «{fdata['name']}» отправлена старшему составу!", show_alert=True)


@dp.callback_query(F.data.startswith("fac_apps:"))
async def cb_fac_apps(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if not (p.get("faction") == fid and (p.get("leader_of") == fid or int(p.get("rank", 1)) >= 8) or is_admin(uid, 3)):
        await callback.answer("Недостаточно прав для просмотра заявок", show_alert=True)
        return
    pending = [a for a in faction_apps.values() if isinstance(a, dict) and a.get("faction") == fid and a.get("status") == "pending"]
    if not pending:
        await callback.answer("Активных заявок нет", show_alert=True)
        return
    lines = [f"📋 **Заявки в «{FACTIONS[fid]['name']}»** (`{len(pending)}`):
"]
    rows = []
    for a in pending[:10]:
        gid = a["game_id"]
        lines.append(f"• **{a['name']}** (`#{gid}`)")
        rows.append([
            InlineKeyboardButton(text=f"✅ Принять #{gid}", callback_data=f"fapp_ok:{fid}:{gid}"),
            InlineKeyboardButton(text=f"❌ Отклонить #{gid}", callback_data=f"fapp_no:{fid}:{gid}"),
        ])
    if callback.message:
        await safe_answer(callback.message, "
".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("fapp_ok:"))
async def cb_fapp_ok(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    actor = get_player(uid, callback.from_user.full_name)
    _, fid, gid_s = callback.data.split(":", 2)
    gid = int(gid_s)
    if not (actor.get("faction") == fid and (actor.get("leader_of") == fid or int(actor.get("rank", 1)) >= 8) or is_admin(uid, 3)):
        await callback.answer("Нет прав", show_alert=True)
        return
    target = find_player_by_game_id(gid)
    if not target:
        await callback.answer("Игрок не найден", show_alert=True)
        return
    target["faction"] = fid
    target["rank"] = 1
    target["f_warns"] = 0
    target["faction_points"] = 0
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "accepted"
    save_state()
    await callback.answer(f"Игрок #{gid} принят!", show_alert=True)
    await safe_send(bot, int(target["tg_id"]), f"🎉 Ваша заявка одобрена! Вы приняты в **{FACTIONS[fid]['name']}** на 1 ранг.", parse_mode="Markdown")


@dp.callback_query(F.data.startswith("fapp_no:"))
async def cb_fapp_no(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    actor = get_player(uid, callback.from_user.full_name)
    _, fid, gid_s = callback.data.split(":", 2)
    gid = int(gid_s)
    if not (actor.get("faction") == fid and (actor.get("leader_of") == fid or int(actor.get("rank", 1)) >= 8) or is_admin(uid, 3)):
        await callback.answer("Нет прав", show_alert=True)
        return
    target = find_player_by_game_id(gid)
    if target:
        app_id = f"{target['tg_id']}_{fid}"
        if app_id in faction_apps:
            faction_apps[app_id]["status"] = "declined"
        save_state()
        await safe_send(bot, int(target["tg_id"]), f"❌ Ваша заявка в **{FACTIONS[fid]['name']}** отклонена.", parse_mode="Markdown")
    await callback.answer(f"Заявка #{gid} отклонена", show_alert=True)


@dp.callback_query(F.data.startswith("fac_mission:"))
async def cb_fac_mission(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return
    if int(p.get("stamina", 100)) < 15 or int(p.get("hunger", 100)) < 10:
        await callback.answer("Нужно минимум 15 выносливости и 10 голода для задания!", show_alert=True)
        return
    now = time.time()
    left = int(45 - (now - float(p.get("last_fmission", 0.0))))
    if left > 0:
        await callback.answer(f"Подождите {left} сек. до следующего задания фракции", show_alert=True)
        return

    fdata = FACTIONS[fid]
    fs = get_fstate(fid)
    rk = int(p.get("rank", 1))
    pay = int(fdata["salary"] * (1 + rk * 0.15)) + random.randint(400, 1100)
    pts = random.randint(15, 30)
    treasury_cut = int(pay * 0.25)

    p["money"] += pay
    p["xp"] += 35
    p["stamina"] = clamp_stat(int(p["stamina"]) - 15)
    p["hunger"] = clamp_stat(int(p["hunger"]) - 10)
    p["faction_points"] = int(p.get("faction_points", 0)) + pts
    p["last_fmission"] = now
    while p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1

    promo_txt = ""
    if rk < 7 and p["faction_points"] >= rk * 100:
        p["rank"] = rk + 1
        promo_txt = f" | Повышение: {get_faction_rank_title(fid, rk + 1)}!"

    fs["treasury"] = int(fs.get("treasury", 0)) + treasury_cut
    fs["rating"] = int(fs.get("rating", 0)) + 5
    save_state()
    await callback.answer(
        f"{fdata['mission_name']}: +{pay} ₽, +{pts} очков службы (+{treasury_cut} ₽ в казну){promo_txt}",
        show_alert=True,
    )


@dp.callback_query(F.data.startswith("fac_salary:"))
async def cb_fac_salary(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return
    fs = get_fstate(fid)
    sal = int(FACTIONS[fid]["salary"] * (1 + (int(p["rank"]) - 1) * 0.12))
    if int(fs.get("treasury", 0)) < sal:
        await callback.answer("В казне фракции недостаточно средств для выплаты оклада!", show_alert=True)
        return
    now = time.time()
    left = int(120 - (now - float(p.get("last_npc", 0.0))))
    if left > 0:
        await callback.answer(f"Следующая зарплата из казны через {left} сек.", show_alert=True)
        return
    fs["treasury"] -= sal
    p["money"] += sal
    p["last_npc"] = now
    save_state()
    await callback.answer(f"Выплачен оклад из казны: +{sal} ₽!", show_alert=True)


@dp.callback_query(F.data.startswith("fac_mats:"))
async def cb_fac_mats(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return
    fs = get_fstate(fid)
    cost = 1500
    if int(fs.get("treasury", 0)) < cost:
        await callback.answer("В казне не хватает 1 500 ₽ на закупку материалов", show_alert=True)
        return
    fs["treasury"] -= cost
    fs["materials"] = int(fs.get("materials", 0)) + 50
    p["faction_points"] = int(p.get("faction_points", 0)) + 10
    save_state()
    await callback.answer("На склад доставлено +50 материалов (+10 очков службы)!", show_alert=True)


@dp.callback_query(F.data.startswith("fac_raid:"))
async def cb_fac_raid(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return
    if int(p.get("stamina", 100)) < 25:
        await callback.answer("Для рейда нужно минимум 25 выносливости!", show_alert=True)
        return
    fs = get_fstate(fid)
    if int(fs.get("materials", 0)) < 100:
        await callback.answer("Для рейда нужно минимум 100 ед. материалов на складе!", show_alert=True)
        return
    now = time.time()
    left = int(180 - (now - float(fs.get("last_raid", 0.0))))
    if left > 0:
        await callback.answer(f"Фракция готовится к следующему рейду (осталось {left} сек.)", show_alert=True)
        return

    fs["materials"] -= 100
    fs["last_raid"] = now
    p["stamina"] = clamp_stat(int(p["stamina"]) - 25)
    p["hunger"] = clamp_stat(int(p["hunger"]) - 15)
    win = random.random() < 0.7
    if win:
        loot = random.randint(8000, 18000)
        fs["treasury"] = int(fs.get("treasury", 0)) + loot
        fs["rating"] = int(fs.get("rating", 0)) + 25
        p["money"] += 2500
        p["faction_points"] = int(p.get("faction_points", 0)) + 40
        save_state()
        await callback.answer(f"Успех! В казну фракции +{loot} ₽, +25 рейтинга, вам +2 500 ₽!", show_alert=True)
    else:
        fs["rating"] = max(0, int(fs.get("rating", 0)) - 5)
        p["hp"] = clamp_stat(int(p["hp"]) - 35)
        save_state()
        await callback.answer("Операция сорвалась! Вы получили ранение (-35 HP).", show_alert=True)


@dp.callback_query(F.data.startswith("fac_bonus:"))
async def cb_fac_bonus(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    actor = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if not (actor.get("faction") == fid and (actor.get("leader_of") == fid or int(actor.get("rank", 1)) >= 9) or is_admin(uid, 4)):
        await callback.answer("Выдавать премии из казны могут 9–10 ранги фракции", show_alert=True)
        return
    fs = get_fstate(fid)
    pool = 10000
    if int(fs.get("treasury", 0)) < pool:
        await callback.answer("В казне недостаточно средств (нужно 10 000 ₽)", show_alert=True)
        return
    members = [u for u in users.values() if isinstance(u, dict) and u.get("faction") == fid]
    if not members:
        await callback.answer("Во фракции нет сотрудников", show_alert=True)
        return
    share = max(500, pool // len(members))
    fs["treasury"] -= pool
    for m in members:
        m["money"] = int(m.get("money", 0)) + share
        await safe_send(bot, int(m["tg_id"]), f"💸 Руководство **{FACTIONS[fid]['name']}** выдало вам премию **+{share} ₽**!", parse_mode="Markdown")
    save_state()
    await callback.answer(f"Премия по {share} ₽ выдана {len(members)} сотрудникам!", show_alert=True)


@dp.callback_query(F.data == "fac_leave_self")
async def cb_fac_leave_self(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = p.get("faction", "none")
    if fid not in FACTIONS:
        await callback.answer("Вы не состоите во фракции", show_alert=True)
        return
    old_name = FACTIONS[fid]["name"]
    p["faction"] = "none"
    p["rank"] = 1
    p["f_warns"] = 0
    p["leader_of"] = None
    p["faction_points"] = 0
    save_state()
    await callback.answer(f"Вы уволились из «{old_name}» по собственному желанию.", show_alert=True)


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
    p["stamina"] = clamp_stat(int(p["stamina"]) - 10)
    p["hunger"] = clamp_stat(int(p["hunger"]) - 8)
    p["last_npc"] = now
    if p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()
    await callback.answer(f"{fdata['npc']}: +{reward} ₽ и +30 XP!", show_alert=True)


@dp.message(Command("fwarn"))
async def cmd_fwarn(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 9 and actor.get("faction") in FACTIONS else None)
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Выдавать выговоры могут 9–10 ранги фракции или админы 3+ ранга.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: `/fwarn <игровой_ID> [причина]`", parse_mode="Markdown")
        return

    gid = int(parts[1])
    reason = parts[2].strip() if len(parts) == 3 and parts[2].strip() else "Нарушение устава"
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    if fid and target.get("faction") != fid:
        await safe_answer(message, "Игрок не состоит в вашей фракции.")
        return

    t_fid = target.get("faction", fid or "none")
    warns = int(target.get("f_warns", 0)) + 1
    if warns >= 3:
        target["faction"] = "none"
        target["rank"] = 1
        target["f_warns"] = 0
        target["leader_of"] = None
        target["faction_points"] = 0
        save_state()
        await safe_answer(message, f"❌ Игрок **{target['name']}** (`#{gid}`) получил **3/3** выговора и уволен из фракции! Причина: _{reason}_", parse_mode="Markdown")
        await safe_send(bot, int(target["tg_id"]), f"❌ Вы уволены из фракции за **3/3 выговоров**. Причина: {reason}", parse_mode="Markdown")
        return

    target["f_warns"] = warns
    save_state()
    f_label = FACTIONS[t_fid]["name"] if t_fid in FACTIONS else "фракции"
    await safe_answer(message, f"⚠️ Игроку **{target['name']}** (`#{gid}`) выдан выговор **`{warns}/3`** в **{f_label}**. Причина: _{reason}_", parse_mode="Markdown")
    await safe_send(bot, int(target["tg_id"]), f"⚠️ Вам выдан выговор **`{warns}/3`** в **{f_label}**. Причина: {reason}", parse_mode="Markdown")


@dp.message(Command("fapps"))
async def cmd_fapps(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    if fid not in FACTIONS or (p.get("leader_of") != fid and int(p.get("rank", 1)) < 8 and not is_admin(uid, 3)):
        await safe_answer(message, "⛔ Просматривать заявки может старший состав фракции (8+ ранг).")
        return
    pending = [a for a in faction_apps.values() if isinstance(a, dict) and a.get("faction") == fid and a.get("status") == "pending"]
    if not pending:
        await safe_answer(message, "📋 Новых заявок во фракцию нет.")
        return
    lines = [f"📋 **Заявки в «{FACTIONS[fid]['name']}»:**
"]
    for a in pending:
        lines.append(f"• **{a['name']}** (`#{a['game_id']}`) — `/faccept {a['game_id']}` или `/fdecline {a['game_id']}`")
    await safe_answer(message, "
".join(lines), parse_mode="Markdown")


@dp.message(Command("faccept"))
async def cmd_faccept(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("faction", "none")
    if fid not in FACTIONS or (actor.get("leader_of") != fid and int(actor.get("rank", 1)) < 8 and not is_admin(uid, 3)):
        await safe_answer(message, "⛔ Принимать заявки могут 8+ ранги фракции.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/faccept <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    target["faction"] = fid
    target["rank"] = 1
    target["f_warns"] = 0
    target["faction_points"] = 0
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "accepted"
    save_state()
    await safe_answer(message, f"✅ Игрок **{target['name']}** (`#{gid}`) принят в **{FACTIONS[fid]['name']}**.", parse_mode="Markdown")
    await safe_send(bot, int(target["tg_id"]), f"🎉 Ваша заявка одобрена! Вы приняты в **{FACTIONS[fid]['name']}**.", parse_mode="Markdown")


@dp.message(Command("fdecline"))
async def cmd_fdecline(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("faction", "none")
    if fid not in FACTIONS or (actor.get("leader_of") != fid and int(actor.get("rank", 1)) < 8 and not is_admin(uid, 3)):
        await safe_answer(message, "⛔ Отклонять заявки могут 8+ ранги фракции.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/fdecline <игровой_ID>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок `#{gid}` не найден.", parse_mode="Markdown")
        return
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "declined"
    save_state()
    await safe_answer(message, f"❌ Заявка игрока **{target['name']}** (`#{gid}`) отклонена.", parse_mode="Markdown")
    await safe_send(bot, int(target["tg_id"]), f"❌ Ваша заявка в **{FACTIONS[fid]['name']}** отклонена.", parse_mode="Markdown")


@dp.message(Command("fdeposit"))
async def cmd_fdeposit(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    if fid not in FACTIONS:
        await safe_answer(message, "Вы не состоите во фракции.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/fdeposit <сумма>`", parse_mode="Markdown")
        return
    try:
        amt = int(parts[1])
    except ValueError:
        await safe_answer(message, "Сумма должна быть числом.")
        return
    if amt <= 0 or p["money"] < amt:
        await safe_answer(message, "Некорректная сумма или недостаточно наличных.")
        return
    fs = get_fstate(fid)
    p["money"] -= amt
    fs["treasury"] = int(fs.get("treasury", 0)) + amt
    p["faction_points"] = int(p.get("faction_points", 0)) + max(1, amt // 500)
    save_state()
    await safe_answer(
        message,
        f"🏦 Вы пополнили казну **{FACTIONS[fid]['name']}** на **+{amt} ₽** (казна: **{fs['treasury']} ₽**).",
        parse_mode="Markdown",
    )


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
    rk_title = get_faction_rank_title(fid, int(p.get("rank", 1)))
    msg_txt = f"📡 **[{FACTIONS[fid]['name']}] {rk_title} {p['name']} (`#{p['game_id']}`):** {parts[1].strip()}"
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
    target["f_warns"] = 0
    target["faction_points"] = 0
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
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 9 and actor.get("faction") in FACTIONS else None)
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Увольнять из фракции могут 9–10 ранги или админы 3+ ранга.")
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
    target["f_warns"] = 0
    target["leader_of"] = None
    target["faction_points"] = 0
    save_state()
    await safe_answer(message, f"🗑 Игрок **{target['name']}** (`#{gid}`) уволен из фракции.", parse_mode="Markdown")


@dp.message(Command("setrank"))
async def cmd_setrank(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 9 and actor.get("faction") in FACTIONS else None)
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Менять ранги могут 9–10 ранги фракции или админы 3+ ранга.")
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
    target_fid = target.get("faction", fid or "dps")
    target["rank"] = rk
    save_state()
    rk_name = get_faction_rank_title(target_fid, rk)
    await safe_answer(
        message,
        f"⭐ Игроку **{target['name']}** (`#{gid}`) назначена должность: **{rk_name}** (`{rk}/10`).",
        parse_mode="Markdown",
    )


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
    lines = ["🏆 **Топ-10 богатейших игроков:**
"]
    for idx, (cap, lvl, name, gid) in enumerate(items[:10], start=1):
        lines.append(f"{idx}. **{name}** (`#{gid}`) — **{cap} ₽** ({lvl} ур.)")
    await safe_answer(message, "
".join(lines), reply_markup=main_kb(uid), parse_mode="Markdown")


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
        "🎬 **Меню Медиа-партнёра:**
"
        "• `/mediaprize <ID> <сумма>` — выдать приз (1..15 000 ₽)
"
        "• `/announce <текст>` — объявление игрокам
"
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
            f"🏦 **Банковский счёт**
"
            f"Наличные: **{p['money']} ₽** | В банке: **{p['bank']} ₽**
"
            "Положить: `/bank put <сумма>`
"
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


@dp.message(Command("resetplayer"))
async def cmd_resetplayer(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 5):
        await safe_answer(message, "⛔ Обнулять аккаунты игроков можно с 5 ранга администратора или создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: `/resetplayer <игровой_ID>`", parse_mode="Markdown")
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

    target_tg_id = int(target["tg_id"])
    if is_creator(target_tg_id):
        await safe_answer(message, "Нельзя обнулить аккаунт создателя.")
        return

    old_name = str(target.get("name") or f"Игрок_{target_tg_id}")
    old_fam_id = target.get("family_id")
    if old_fam_id and str(old_fam_id) in families:
        fdata = families[str(old_fam_id)]
        members = list(fdata.get("members") or [])
        if target_tg_id in members:
            members.remove(target_tg_id)
            fdata["members"] = members
        if fdata.get("owner_uid") == target_tg_id:
            if members:
                fdata["owner_uid"] = members[0]
                next_u = users.get(str(members[0]))
                fdata["owner_name"] = next_u.get("name") if isinstance(next_u, dict) else "Глава"
            else:
                del families[str(old_fam_id)]

    for b in businesses.values():
        if isinstance(b, dict) and b.get("owner_uid") == target_tg_id:
            b["owner_uid"] = None
            b["owner_name"] = None
            b["cash"] = 0
            b["last_collect"] = 0.0

    fresh = normalize_player({"name": old_name, "game_id": gid}, target_tg_id)
    fresh["money"] = 0
    fresh["bank"] = 0
    users[str(target_tg_id)] = fresh
    save_state()

    await safe_answer(
        message,
        f"♻️ Прогресс игрока **{old_name}** (`#{gid}`) полностью обнулён (баланс `0 ₽`, 1 уровень, без имущества/фракции/семьи).",
        parse_mode="Markdown",
    )
    await safe_send(
        bot,
        target_tg_id,
        "♻️ Ваш игровой прогресс был обнулён администрацией.",
        parse_mode="Markdown",
    )


@dp.message(Command("wipeall"))
async def cmd_wipeall(message: Message):
    uid = message.from_user.id
    if not is_creator(uid):
        await safe_answer(message, "⛔ Полный вайп сервера доступен только создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or parts[1].strip().upper() != "CONFIRM":
        await safe_answer(
            message,
            "⚠️ **Внимание!** Это полностью очистит базу игроков, бизнесов, семей, промокодов и тикетов.
"
            "Для подтверждения введите: `/wipeall CONFIRM`",
            parse_mode="Markdown",
        )
        return

    creator_backup = None
    if CREATOR_ID and str(CREATOR_ID) in users and isinstance(users[str(CREATOR_ID)], dict):
        creator_backup = dict(users[str(CREATOR_ID)])

    users.clear()
    faction_apps.clear()
    families.clear()
    promocodes.clear()
    support_tickets.clear()
    businesses.clear()
    for bid, bdef in DEFAULT_BUSINESSES.items():
        businesses[bid] = dict(bdef)

    if creator_backup:
        users[str(CREATOR_ID)] = normalize_player(creator_backup, CREATOR_ID)

    save_state()
    await safe_answer(
        message,
        "🧹 **Полный вайп выполнен!** База сервера сброшена к чистому состоянию.",
        reply_markup=main_kb(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("tech"))
@dp.message(Command("maint"))
async def cmd_maintenance(message: Message):
    global maintenance_mode, maintenance_reason
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Управлять режимом технических работ можно с 4 ранга администратора.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) == 1:
        status_txt = "ВКЛЮЧЕНЫ 🛠" if maintenance_mode else "ВЫКЛЮЧЕНЫ ✅"
        await safe_answer(
            message,
            f"🛠 **Режим технических работ:** **{status_txt}**
"
            f"Причина: _{maintenance_reason}_

"
            "Включить: `/tech on [причина]`
"
            "Выключить: `/tech off`",
            parse_mode="Markdown",
        )
        return

    mode_arg = parts[1].strip().lower()
    if mode_arg in {"on", "1", "true", "да"}:
        maintenance_mode = True
        if len(parts) == 3 and parts[2].strip():
            maintenance_reason = parts[2].strip()
        save_state()
        await safe_answer(
            message,
            f"🛠 **Технические работы ВКЛЮЧЕНЫ.**
"
            f"Причина: _{maintenance_reason}_
"
            "Игрокам бот будет отвечать уведомлением о техработах, админы 1+ ранга и создатель продолжают работу.",
            parse_mode="Markdown",
        )
    elif mode_arg in {"off", "0", "false", "нет"}:
        maintenance_mode = False
        save_state()
        await safe_answer(
            message,
            "✅ **Технические работы ВЫКЛЮЧЕНЫ.** Бот снова доступен всем игрокам.",
            parse_mode="Markdown",
        )
    else:
        await safe_answer(
            message,
            "Формат: `/tech on [причина]` или `/tech off`",
            parse_mode="Markdown",
        )


async def passive_vitals_loop() -> None:
    """Каждые 2 минуты снижает голод и восстанавливает выносливость, сохраняя состояние."""
    while True:
        await asyncio.sleep(120)
        changed = False
        for k, u in users.items():
            if not isinstance(u, dict):
                continue
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            normalize_player(u, tg_id)
            old_h = int(u["hunger"])
            old_s = int(u["stamina"])
            old_hp = int(u["hp"])

            new_h = clamp_stat(old_h - 2)
            if new_h < 15:
                new_s = clamp_stat(old_s - 4)
                new_hp = clamp_stat(old_hp - 3)
            else:
                new_s = clamp_stat(old_s + 8)
                new_hp = old_hp

            if new_h != old_h or new_s != old_s or new_hp != old_hp:
                u["hunger"] = new_h
                u["stamina"] = new_s
                u["hp"] = new_hp
                changed = True

        if changed:
            save_state()


async def main() -> None:
    load_state()
    save_state()
    bot = Bot(token=BOT_TOKEN)
    asyncio.create_task(passive_vitals_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
