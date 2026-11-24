import asyncio
import html
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

NICK_RE = re.compile(r"^[А-ЯЁA-Z][а-яёa-z]{1,14}_[А-ЯЁA-Z][а-яёa-z]{1,14}$")
NICK_CHANGE_COST = 20000
NICK_CHANGE_COOLDOWN = 3600  # 1 час

PAY_MIN_AMOUNT = 100
PAY_MAX_AMOUNT = 5_000_000
PAY_COMMISSION_RATE = 0.03  # 3% комиссия за перевод

DEP_RADIO_MIN_RANK = 6
DEP_RADIO_COOLDOWN = 10

MAX_OPEN_TICKETS_PER_USER = 2

SUPPORT_CATEGORIES: dict[str, str] = {
    "quest": "❓ Вопрос по игре",
    "bug": "🐛 Баг / Проблема",
    "report": "⚖️ Жалоба на игрока",
    "donate": "💸 Донат / Имущество",
    "fac": "🏛 Фракции / Ранги",
}

MAIN_MENU_BUTTONS: set[str] = {
    "👤 Профиль",
    "💵 Работа",
    "🍔 Еда и отдых",
    "🏥 Больница",
    "🎰 Казино",
    "🏛 Фракции",
    "🏢 Бизнесы",
    "🏠 Недвижимость",
    "🚗 Автосалон",
    "👨‍👩‍👧‍👦 Семья",
    "🏆 Топ-10",
    "🎫 Поддержка",
    "📖 Команды",
    "🎬 Медиа",
    "🛟 Хелперка",
}

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

MEDIA_RANKS: dict[int, dict[str, Any]] = {
    1: {
        "title": "Начинающий медиа",
        "max_prize": 5000,
        "max_promo_money": 25000,
        "max_promo_uses": 50,
        "announce_cd": 600,
        "salary_bonus": 2000,
        "perm_desc": "Призы до 5 000 ₽, промокоды до 25 000 ₽ (50 акт.)",
    },
    2: {
        "title": "Младший контент-мейкер",
        "max_prize": 10000,
        "max_promo_money": 50000,
        "max_promo_uses": 100,
        "announce_cd": 480,
        "salary_bonus": 4000,
        "perm_desc": "Призы до 10 000 ₽, промокоды до 50 000 ₽ (100 акт.)",
    },
    3: {
        "title": "Контент-мейкер",
        "max_prize": 15000,
        "max_promo_money": 100000,
        "max_promo_uses": 200,
        "announce_cd": 360,
        "salary_bonus": 7000,
        "perm_desc": "Призы до 15 000 ₽, промокоды до 100 000 ₽ (200 акт.)",
    },
    4: {
        "title": "Стример проекта",
        "max_prize": 25000,
        "max_promo_money": 150000,
        "max_promo_uses": 350,
        "announce_cd": 240,
        "salary_bonus": 11000,
        "perm_desc": "Призы до 25 000 ₽, промокоды до 150 000 ₽ (350 акт.)",
    },
    5: {
        "title": "Ведущий стример",
        "max_prize": 40000,
        "max_promo_money": 250000,
        "max_promo_uses": 500,
        "announce_cd": 180,
        "salary_bonus": 16000,
        "perm_desc": "Призы до 40 000 ₽, промокоды до 250 000 ₽ (500 акт.)",
    },
    6: {
        "title": "Медиа-партнёр",
        "max_prize": 60000,
        "max_promo_money": 350000,
        "max_promo_uses": 800,
        "announce_cd": 120,
        "salary_bonus": 22000,
        "perm_desc": "Призы до 60 000 ₽, промокоды до 350 000 ₽ (800 акт.)",
    },
    7: {
        "title": "Старший медиа-партнёр",
        "max_prize": 100000,
        "max_promo_money": 500000,
        "max_promo_uses": 1500,
        "announce_cd": 60,
        "salary_bonus": 30000,
        "perm_desc": "Призы до 100 000 ₽, промокоды до 500 000 ₽ (1 500 акт.)",
    },
    8: {
        "title": "Руководитель медиа-отдела",
        "max_prize": 200000,
        "max_promo_money": 1000000,
        "max_promo_uses": 5000,
        "announce_cd": 30,
        "salary_bonus": 45000,
        "perm_desc": "Призы до 200 000 ₽, промокоды до 1 000 000 ₽, управление медиа (1–7)",
    },
}

MEDIA_MAX_RANK = max(MEDIA_RANKS.keys())

FACTIONS: dict[str, dict[str, Any]] = {
    "mvd": {
        "name": "МВД России",
        "type": "law",
        "salary": 1900,
        "npc": "Полковник Громов",
        "min_lvl": 1,
        "mission_name": "Патрулирование области",
        "ranks": {
            1: "Рядовой",
            2: "Младший сержант",
            3: "Сержант",
            4: "Старший сержант",
            5: "Прапорщик",
            6: "Младший лейтенант",
            7: "Лейтенант",
            8: "Старший лейтенант",
            9: "Капитан",
            10: "Майор",
            11: "Подполковник",
            12: "Полковник",
            13: "Генерал-майор",
        },
    },
    "dps": {
        "name": "ГИБДД / ДПС",
        "type": "law",
        "salary": 1800,
        "npc": "Инспектор Воробьёв",
        "min_lvl": 1,
        "mission_name": "Патруль поста ДПС",
        "ranks": {
            1: "Рядовой",
            2: "Младший сержант",
            3: "Сержант",
            4: "Старший сержант",
            5: "Прапорщик",
            6: "Младший лейтенант",
            7: "Лейтенант",
            8: "Старший лейтенант",
            9: "Капитан",
            10: "Майор",
            11: "Подполковник",
            12: "Полковник",
            13: "Генерал-майор",
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
            1: "Рядовой",
            2: "Младший сержант",
            3: "Сержант",
            4: "Старший сержант",
            5: "Прапорщик",
            6: "Младший лейтенант",
            7: "Лейтенант",
            8: "Старший лейтенант",
            9: "Капитан",
            10: "Майор",
            11: "Подполковник",
            12: "Полковник",
            13: "Генерал-майор",
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
            1: "Стажёр",
            2: "Младший оперативник",
            3: "Оперативник",
            4: "Старший оперативник",
            5: "Специальный агент",
            6: "Старший агент",
            7: "Начальник отдела",
            8: "Куратор направления",
            9: "Инспектор УСБ",
            10: "Заместитель начальника УФСБ",
            11: "Начальник УФСБ",
            12: "Первый заместитель директора",
            13: "Директор ФСБ",
        },
    },
    "fsin": {
        "name": "ФСИН России",
        "type": "law",
        "salary": 2000,
        "npc": "Майор Калинин",
        "min_lvl": 1,
        "mission_name": "Конвоирование и режим",
        "ranks": {
            1: "Рядовой внутренней службы",
            2: "Младший сержант вн. сл.",
            3: "Сержант вн. сл.",
            4: "Старший сержант вн. сл.",
            5: "Прапорщик вн. сл.",
            6: "Младший лейтенант вн. сл.",
            7: "Лейтенант вн. сл.",
            8: "Старший лейтенант вн. сл.",
            9: "Капитан вн. сл.",
            10: "Майор вн. сл.",
            11: "Подполковник вн. сл.",
            12: "Полковник вн. сл.",
            13: "Генерал-майор вн. сл.",
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
            1: "Рядовой",
            2: "Младший сержант",
            3: "Сержант",
            4: "Старший сержант",
            5: "Прапорщик",
            6: "Младший лейтенант",
            7: "Лейтенант",
            8: "Старший лейтенант",
            9: "Капитан",
            10: "Майор",
            11: "Подполковник",
            12: "Полковник",
            13: "Генерал-майор",
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
            1: "Интерн",
            2: "Фельдшер",
            3: "Младший медбрат / медсестра",
            4: "Врач-терапевт",
            5: "Врач-хирург",
            6: "Врач-специалист",
            7: "Старший врач",
            8: "Координатор отделения",
            9: "Заведующий отделением",
            10: "Главный специалист",
            11: "Заместитель главного врача",
            12: "И. о. главного врача",
            13: "Главный врач",
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
            10: "Зам. программного директора",
            11: "Программный директор",
            12: "Заместитель директора ТРК",
            13: "Директор ТРК",
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
            3: "Младший сержант",
            4: "Сержант",
            5: "Старший сержант",
            6: "Прапорщик",
            7: "Младший лейтенант",
            8: "Лейтенант",
            9: "Старший лейтенант",
            10: "Капитан",
            11: "Майор",
            12: "Подполковник",
            13: "Полковник / Генерал-майор",
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
            9: "Министр",
            10: "Заместитель председателя",
            11: "Председатель правительства",
            12: "Вице-губернатор",
            13: "Губернатор области",
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
            8: "Авторитет",
            9: "Смотрящий",
            10: "Бригадир",
            11: "Положенец",
            12: "Зам. вора в законе",
            13: "Вор в законе",
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
            8: "Старший авторитет",
            9: "Смотрящий",
            10: "Зам. смотрящего",
            11: "Правая рука",
            12: "Заместитель бати",
            13: "Батя",
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
    "khrushchevka": {"name": "Квартира в хрущёвке", "price": 450000, "bonus_bank": 500},
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
    choosing_category = State()
    waiting_message = State()
    replying_ticket = State()


def esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=False)


def clamp_stat(val: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(val)))


def validate_rp_nick(nick: str) -> tuple[bool, str]:
    clean = nick.strip()
    if len(clean) < 5 or len(clean) > 31:
        return False, "Ник должен быть в формате <code>Имя_Фамилия</code> (от 5 до 31 символа, без пробелов)."
    if not NICK_RE.match(clean):
        return False, "Неверный формат ника. Используйте <code>Имя_Фамилия</code> (например, <code>Иван_Волков</code> или <code>Ivan_Volkov</code>)."
    return True, clean


def is_nick_taken(nick: str, exclude_tg_id: int | None = None) -> bool:
    target_low = nick.strip().lower()
    for k, u in users.items():
        if not isinstance(u, dict):
            continue
        try:
            tg_id = int(u.get("tg_id") or k)
        except ValueError:
            continue
        if exclude_tg_id is not None and tg_id == exclude_tg_id:
            continue
        existing_name = str(u.get("name") or "").strip().lower()
        if existing_name == target_low:
            return True
    return False


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
    raw_age = u.get("age")
    if raw_age is not None:
        try:
            age_val = int(raw_age)
            u["age"] = age_val if 18 <= age_val <= 90 else None
        except (ValueError, TypeError):
            u["age"] = None
    else:
        u["age"] = None
    u["last_nick_change"] = float(u.get("last_nick_change", 0.0) or 0.0)
    u["lvl"] = max(1, int(u.get("lvl", 1)))
    u["xp"] = max(0, int(u.get("xp", 0)))
    u["money"] = int(u.get("money", 5000))
    u["bank"] = int(u.get("bank", 0))
    u["hp"] = clamp_stat(u.get("hp", 100))
    u["hunger"] = clamp_stat(u.get("hunger", 100))
    u["stamina"] = clamp_stat(u.get("stamina", 100))
    u["faction"] = str(u.get("faction") or "none")
    u["rank"] = max(1, min(13, int(u.get("rank", 1))))
    u["f_warns"] = max(0, min(3, int(u.get("f_warns", 0))))
    u["leader_of"] = u.get("leader_of") if u.get("leader_of") in FACTIONS else None
    u["admin_lvl"] = max(0, min(8, int(u.get("admin_lvl", 0))))
    u["helper_lvl"] = max(0, min(8, int(u.get("helper_lvl", 0))))
    u["helper_answers"] = max(0, int(u.get("helper_answers", 0)))
    u["faction_points"] = max(0, int(u.get("faction_points", 0)))
    u["last_fmission"] = float(u.get("last_fmission", 0.0))

    raw_media_lvl = u.get("media_lvl")
    if raw_media_lvl is not None:
        try:
            m_lvl = max(0, min(MEDIA_MAX_RANK, int(raw_media_lvl)))
        except (ValueError, TypeError):
            m_lvl = 0
    elif bool(u.get("is_media", False)):
        m_lvl = 1
    else:
        m_lvl = 0
    u["media_lvl"] = m_lvl
    u["is_media"] = bool(m_lvl > 0)
    u["media_prizes_given"] = max(0, int(u.get("media_prizes_given", 0)))
    u["media_promos_created"] = max(0, int(u.get("media_promos_created", 0)))
    u["last_media_announce"] = float(u.get("last_media_announce", 0.0) or 0.0)
    u["last_media_salary"] = float(u.get("last_media_salary", 0.0) or 0.0)

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
    u["dep_mute_until"] = float(u.get("dep_mute_until", 0.0) or 0.0)
    u["last_dep_msg"] = float(u.get("last_dep_msg", 0.0) or 0.0)
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


def get_media_lvl(uid: int) -> int:
    if is_creator(uid):
        return MEDIA_MAX_RANK
    u = users.get(str(uid))
    if not isinstance(u, dict):
        return 0
    raw_lvl = u.get("media_lvl")
    if raw_lvl is not None:
        try:
            return max(0, min(MEDIA_MAX_RANK, int(raw_lvl)))
        except (ValueError, TypeError):
            return 0
    return 1 if bool(u.get("is_media", False)) else 0


def get_media_title(lvl: int) -> str:
    if lvl <= 0:
        return "Нет"
    info = MEDIA_RANKS.get(lvl)
    return f"{lvl} ранг ({info['title']})" if info else f"{lvl} ранг"


def get_media_spec(uid: int) -> dict[str, Any] | None:
    lvl = get_media_lvl(uid)
    if lvl <= 0:
        return None
    base = dict(MEDIA_RANKS.get(lvl, MEDIA_RANKS[1]))
    base["lvl"] = lvl
    if is_creator(uid):
        base["max_prize"] = 1_000_000
        base["max_promo_money"] = 5_000_000
        base["max_promo_uses"] = 100_000
        base["announce_cd"] = 0
        base["salary_bonus"] = 50_000
    return base


def is_media(uid: int, min_lvl: int = 1) -> bool:
    if is_creator(uid):
        return True
    return get_media_lvl(uid) >= min_lvl


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
    return str(u.get("faction") or "") in {"mvd", "dps", "pps", "fsb", "fsin", "vo"} or is_admin(int(u.get("tg_id", 0)), 1)


def load_state() -> None:
    global next_game_id, next_ticket_id, maintenance_mode, maintenance_reason
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
                "creator_id": pdata.get("creator_id"),
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
                    text = f"🚫 Ваш аккаунт заблокирован.\nПричина: {esc(reason)}"
                    if isinstance(event, Message):
                        await safe_answer(event, text, parse_mode="HTML")
                    elif isinstance(event, CallbackQuery):
                        await event.answer(f"🚫 Аккаунт заблокирован. Причина: {reason}", show_alert=True)
                    return
                tb_until = float(u.get("tempban_until", 0.0) or 0.0)
                if tb_until > 0:
                    now_ts = time.time()
                    if now_ts < tb_until:
                        rem_txt = format_duration(tb_until - now_ts)
                        tb_reason = u.get("tempban_reason") or "Нарушение правил сервера"
                        text = (
                            f"⏳ Ваш аккаунт временно заблокирован.\n"
                            f"Осталось: <b>{esc(rem_txt)}</b>\n"
                            f"Причина: {esc(tb_reason)}"
                        )
                        if isinstance(event, Message):
                            await safe_answer(event, text, parse_mode="HTML")
                        elif isinstance(event, CallbackQuery):
                            await event.answer(f"⏳ Временный бан ({rem_txt}). Причина: {tb_reason}", show_alert=True)
                        return
                    else:
                        u["tempban_until"] = 0.0
                        u["tempban_reason"] = ""
                        save_state()
        if uid is not None and maintenance_mode and not is_admin(uid, 1):
            m_text = f"🛠 <b>Технические работы</b>\n{esc(maintenance_reason)}"
            if isinstance(event, Message):
                await safe_answer(event, m_text, parse_mode="HTML")
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


def get_user_open_tickets(uid: int) -> list[dict[str, Any]]:
    res = []
    for t in support_tickets.values():
        if isinstance(t, dict) and int(t.get("user_id", 0)) == uid and t.get("status") != "closed":
            res.append(t)
    res.sort(key=lambda x: int(x.get("id", 0)), reverse=True)
    return res


def render_support_menu_kb(uid: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="✍️ Новое обращение", callback_data="sup_new")]
    ]
    for t in get_user_open_tickets(uid)[:3]:
        tid = str(t["id"])
        rows.append([
            InlineKeyboardButton(text=f"📂 Тикет #{tid}", callback_data=f"sup_view:{tid}"),
            InlineKeyboardButton(text=f"💬 Дописать #{tid}", callback_data=f"sup_ureply:{tid}"),
            InlineKeyboardButton(text=f"🔒 Закрыть #{tid}", callback_data=f"sup_uclose:{tid}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def render_categories_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"sup_cat:{key}")]
        for key, label in SUPPORT_CATEGORIES.items()
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="sup_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        await safe_send(bot, staff_id, text_msg, parse_mode="HTML")


@dp.message(Command("support"))
@dp.message(F.text == "🎫 Поддержка")
async def cmd_support(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await state.clear()

    raw_text = (message.text or "").strip()
    parts = raw_text.split(maxsplit=1)
    if raw_text.startswith("/support") and len(parts) == 2 and parts[1].strip():
        await create_support_ticket(message, bot, p, parts[1].strip()[:1000], category_key="quest")
        return

    my_open = get_user_open_tickets(uid)
    status_line = (
        f"Открытых обращений: <b><code>{len(my_open)}/{MAX_OPEN_TICKETS_PER_USER}</code></b>"
        if my_open
        else "У вас пока нет открытых обращений."
    )
    await safe_answer(
        message,
        f"🎫 <b>Служба поддержки Criminal Russia RP</b>\n"
        f"{status_line}\n\n"
        f"• Нажмите <b>«✍️ Новое обращение»</b>, чтобы выбрать тему и описать ситуацию.\n"
        f"• Быстрая команда: <code>/support &lt;ваш вопрос&gt;</code>",
        reply_markup=render_support_menu_kb(uid),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "sup_menu")
async def cb_sup_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    my_open = get_user_open_tickets(uid)
    text = (
        f"🎫 <b>Служба поддержки Criminal Russia RP</b>\n"
        f"Открытых обращений: <b><code>{len(my_open)}/{MAX_OPEN_TICKETS_PER_USER}</code></b>"
    )
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=render_support_menu_kb(uid), parse_mode="HTML")
        except Exception:
            await safe_answer(callback.message, text, reply_markup=render_support_menu_kb(uid), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "sup_new")
async def cb_sup_new(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    my_open = get_user_open_tickets(uid)
    if len(my_open) >= MAX_OPEN_TICKETS_PER_USER:
        await callback.answer(
            f"Максимум {MAX_OPEN_TICKETS_PER_USER} открытых тикета одновременно. Закройте старый или дождитесь ответа.",
            show_alert=True,
        )
        return
    await state.set_state(SupportStates.choosing_category)
    if callback.message:
        try:
            await callback.message.edit_text(
                "📌 <b>Выберите категорию обращения:</b>",
                reply_markup=render_categories_kb(),
                parse_mode="HTML",
            )
        except Exception:
            await safe_answer(callback.message, "📌 <b>Выберите категорию обращения:</b>", reply_markup=render_categories_kb(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(SupportStates.choosing_category, F.data.startswith("sup_cat:"))
async def cb_sup_cat(callback: CallbackQuery, state: FSMContext):
    cat_key = callback.data.split(":", 1)[1]
    if cat_key not in SUPPORT_CATEGORIES:
        await callback.answer("Неизвестная категория", show_alert=True)
        return
    await state.update_data(support_category=cat_key)
    await state.set_state(SupportStates.waiting_message)
    if callback.message:
        try:
            await callback.message.edit_text(
                f"✍️ <b>Категория: {esc(SUPPORT_CATEGORIES[cat_key])}</b>\n\n"
                f"Напишите ваш вопрос или описание проблемы <b>одним сообщением</b>.\n"
                f"Для отмены отправьте <code>/cancel</code>.",
                parse_mode="HTML",
            )
        except Exception:
            await safe_answer(
                callback.message,
                f"✍️ <b>Категория: {esc(SUPPORT_CATEGORIES[cat_key])}</b>\n\nНапишите ваш вопрос или описание проблемы.",
                parse_mode="HTML",
            )
    await callback.answer()


@dp.callback_query(F.data.startswith("sup_ureply:"))
async def cb_sup_ureply(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    tid = callback.data.split(":", 1)[1]
    ticket = support_tickets.get(tid)
    if not ticket or int(ticket.get("user_id", 0)) != uid or ticket.get("status") == "closed":
        await callback.answer("Тикет закрыт или не найден", show_alert=True)
        return
    await state.update_data(reply_ticket_id=tid)
    await state.set_state(SupportStates.replying_ticket)
    await callback.answer()
    if callback.message:
        await safe_answer(
            callback.message,
            f"💬 Напишите дополнительное сообщение по тикету <b><code>#{esc(tid)}</code></b> (или <code>/cancel</code> для отмены):",
            parse_mode="HTML",
        )


@dp.message(SupportStates.waiting_message)
async def process_support_text(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    text_body = (message.text or "").strip()

    if not text_body or text_body in MAIN_MENU_BUTTONS or text_body.startswith("/"):
        await state.clear()
        await safe_answer(
            message,
            "⚠️ Ввод обращения отменён (выбрана команда или кнопка меню).",
            reply_markup=main_kb(uid),
        )
        return

    if len(text_body) < 4:
        await safe_answer(message, "⚠️ Опишите вопрос подробнее (минимум 4 символа) или отправьте <code>/cancel</code>.", parse_mode="HTML")
        return

    data = await state.get_data()
    cat_key = str(data.get("support_category") or "quest")
    await state.clear()
    await create_support_ticket(message, bot, p, text_body[:1000], category_key=cat_key)


@dp.message(SupportStates.replying_ticket)
async def process_user_ticket_reply(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    text_body = (message.text or "").strip()

    if not text_body or text_body in MAIN_MENU_BUTTONS or text_body.startswith("/"):
        await state.clear()
        await safe_answer(
            message,
            "⚠️ Ответ в тикет отменён (выбрана команда или кнопка меню).",
            reply_markup=main_kb(uid),
        )
        return

    data = await state.get_data()
    tid = str(data.get("reply_ticket_id") or "")
    await state.clear()

    ticket = support_tickets.get(tid)
    if not ticket or int(ticket.get("user_id", 0)) != uid or ticket.get("status") == "closed":
        await safe_answer(message, "❌ Тикет уже закрыт или не найден.", reply_markup=main_kb(uid))
        return

    ticket["status"] = "open"
    ticket.setdefault("messages", []).append({
        "from": "player",
        "name": str(p["name"]),
        "text": text_body[:1000],
    })
    save_state()

    await safe_answer(
        message,
        f"✅ Сообщение добавлено в тикет <b><code>#{esc(tid)}</code></b>! Ожидайте ответа поддержки.",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )
    await notify_staff_ticket(
        bot,
        tid,
        f"💬 <b>Новое сообщение в тикете <code>#{esc(tid)}</code></b> от <b>{esc(p['name'])}</b> (<code>#{p['game_id']}</code>):\n"
        f"{esc(text_body[:1000])}\n\n"
        f"Ответить: <code>/answer {esc(tid)} &lt;текст&gt;</code> | Закрыть: <code>/closeticket {esc(tid)}</code>",
    )


@dp.callback_query(F.data.startswith("sup_view:"))
async def cb_sup_view(callback: CallbackQuery):
    uid = callback.from_user.id
    tid = callback.data.split(":", 1)[1]
    ticket = support_tickets.get(tid)
    if not ticket or int(ticket.get("user_id", 0)) != uid:
        await callback.answer("Тикет не найден", show_alert=True)
        return

    msgs = ticket.get("messages") or []
    history_lines = []
    for m in msgs[-6:]:
        who = "Вы" if m.get("from") == "player" else f"Поддержка ({m.get('name', 'Хелпер')})"
        history_lines.append(f"• <b>{esc(who)}:</b> {esc(m.get('text', ''))}")

    status_map = {"open": "🟢 Открыт", "answered": "🔵 Есть ответ", "closed": "🔒 Закрыт"}
    st_label = status_map.get(str(ticket.get("status", "open")), "Открыт")
    body = (
        f"📂 <b>Тикет <code>#{esc(tid)}</code></b> — {st_label}\n"
        f"Категория: <b>{esc(ticket.get('category_label', '❓ Вопрос по игре'))}</b>\n\n"
        + ("\n".join(history_lines) if history_lines else "<i>Сообщений пока нет</i>")
    )
    await callback.answer()
    if callback.message:
        await safe_answer(callback.message, body, parse_mode="HTML")


@dp.callback_query(F.data.startswith("sup_uclose:"))
async def cb_sup_uclose(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    tid = callback.data.split(":", 1)[1]
    ticket = support_tickets.get(tid)
    if not ticket or int(ticket.get("user_id", 0)) != uid:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    ticket["status"] = "closed"
    u = users.get(str(uid))
    if isinstance(u, dict) and u.get("active_ticket") == tid:
        u["active_ticket"] = None
    save_state()
    await callback.answer(f"Тикет #{tid} закрыт", show_alert=True)
    if callback.message:
        try:
            await callback.message.edit_text(
                f"🔒 Тикет <b><code>#{esc(tid)}</code></b> закрыт вами.",
                reply_markup=render_support_menu_kb(uid),
                parse_mode="HTML",
            )
        except Exception:
            await safe_answer(callback.message, f"🔒 Тикет <b><code>#{esc(tid)}</code></b> закрыт вами.", parse_mode="HTML")
    await notify_staff_ticket(bot, tid, f"ℹ️ Игрок сам закрыл тикет <code>#{esc(tid)}</code>.")


async def create_support_ticket(
    message: Message,
    bot: Bot,
    p: dict[str, Any],
    body: str,
    category_key: str = "quest",
) -> None:
    global next_ticket_id
    uid = int(p["tg_id"])
    if len(get_user_open_tickets(uid)) >= MAX_OPEN_TICKETS_PER_USER:
        await safe_answer(
            message,
            f"⚠️ У вас уже открыто максимальное число тикетов (<code>{MAX_OPEN_TICKETS_PER_USER}</code>). Дождитесь ответа или закройте текущий.",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return

    tid = str(next_ticket_id)
    next_ticket_id += 1
    cat_label = SUPPORT_CATEGORIES.get(category_key, "❓ Вопрос по игре")

    support_tickets[tid] = {
        "id": tid,
        "user_id": uid,
        "game_id": int(p["game_id"]),
        "user_name": str(p["name"]),
        "category": category_key,
        "category_label": cat_label,
        "status": "open",
        "created_at": int(time.time()),
        "messages": [{"from": "player", "name": str(p["name"]), "text": body}],
    }
    p["active_ticket"] = tid
    save_state()

    await safe_answer(
        message,
        f"✅ Обращение <b><code>#{esc(tid)}</code></b> отправлено в поддержку!\n"
        f"Категория: <b>{esc(cat_label)}</b>\n"
        f"Ожидайте ответа хелперов или администрации.",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )
    await notify_staff_ticket(
        bot,
        tid,
        f"🎫 <b>Новый тикет <code>#{esc(tid)}</code></b> | {esc(cat_label)}\n"
        f"Игрок: <b>{esc(p['name'])}</b> (<code>#{p['game_id']}</code>, TG: <code>{uid}</code>, ур. <code>{p['lvl']}</code>)\n"
        f"Текст: {esc(body)}\n\n"
        f"Ответить: <code>/answer {esc(tid)} &lt;текст&gt;</code> | Закрыть: <code>/closeticket {esc(tid)}</code>",
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    cur = await state.get_state()
    if cur is None:
        await safe_answer(message, "Нет активного действия для отмены.", reply_markup=main_kb(message.from_user.id))
        return
    await state.clear()
    await safe_answer(message, "Действие отменено.", reply_markup=main_kb(message.from_user.id))


@dp.message(Command("tickets"))
@dp.message(F.text == "🛟 Хелперка")
async def cmd_tickets(message: Message):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Раздел доступен только хелперам и администрации.")
        return

    active_list = [
        t for t in support_tickets.values()
        if isinstance(t, dict) and t.get("status") in {"open", "answered"}
    ]
    active_list.sort(key=lambda x: (0 if x.get("status") == "open" else 1, int(x.get("id", 0))))
    if not active_list:
        await safe_answer(message, "🛟 Открытых обращений в поддержку сейчас нет.", reply_markup=main_kb(uid))
        return

    lines = [f"🛟 <b>Активные тикеты</b> (<code>{len(active_list)}</code>):\n"]
    kb_rows = []
    for t in active_list[:15]:
        msgs = t.get("messages") or []
        last_txt = msgs[-1].get("text", "") if msgs else ""
        st_badge = "🟢 Ждёт ответа" if t.get("status") == "open" else "🔵 Отвечен"
        cat_txt = t.get("category_label") or "❓ Вопрос"
        lines.append(
            f"• Тикет <b><code>#{esc(t['id'])}</code></b> [{st_badge}] — <b>{esc(t.get('user_name'))}</b> (<code>#{t.get('game_id')}</code>) | {esc(cat_txt)}\n"
            f"  <i>{esc(last_txt[:100])}</i>"
        )
        kb_rows.append([
            InlineKeyboardButton(text=f"🔒 Закрыть #{t['id']}", callback_data=f"tclose:{t['id']}"),
        ])
    st = get_player(uid, message.from_user.full_name)
    lines.append(f"\nВаш ранг: <b>{esc(get_helper_title(int(st.get('helper_lvl', 0))))}</b> | Ответов: <code>{st.get('helper_answers', 0)}</code>")
    lines.append("Команды: <code>/answer &lt;ID&gt; &lt;текст&gt;</code> | <code>/closeticket &lt;ID&gt;</code> | <code>/helpers</code>")
    await safe_answer(
        message,
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else main_kb(uid),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("tclose:"))
async def cb_close_ticket(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    if not is_helper(uid, 1):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    tid = callback.data.split(":", 1)[1]
    ticket = support_tickets.get(tid)
    if not ticket:
        await callback.answer("Тикет не найден", show_alert=True)
        return
    ticket["status"] = "closed"
    target_uid = int(ticket["user_id"])
    u = users.get(str(target_uid))
    if isinstance(u, dict) and u.get("active_ticket") == tid:
        u["active_ticket"] = None
    save_state()
    await callback.answer(f"Тикет #{tid} закрыт", show_alert=True)
    await safe_send(
        bot,
        target_uid,
        f"🔒 Ваш тикет в поддержку <code>#{esc(tid)}</code> закрыт. Если появятся новые вопросы — нажмите «🎫 Поддержка» или напишите <code>/support</code>.",
        parse_mode="HTML",
    )


@dp.message(Command("answer"))
async def cmd_answer_ticket(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Отвечать на тикеты могут хелперы и администраторы.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await safe_answer(message, "Формат: <code>/answer &lt;ID_тикета&gt; &lt;текст ответа&gt;</code>", parse_mode="HTML")
        return

    tid = parts[1].lstrip("#").strip()
    reply_text = parts[2].strip()
    ticket = support_tickets.get(tid)
    if not ticket:
        await safe_answer(message, f"Тикет <code>#{esc(tid)}</code> не найден.", parse_mode="HTML")
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
            promo_note = f"\n🎉 Поздравляем! Вы повышены до ранга <b>{esc(get_helper_title(h_lvl + 1))}</b>!"

    ticket["status"] = "answered"
    ticket.setdefault("messages", []).append({
        "from": "staff",
        "name": f"{staff['name']} [{h_info['title']}]",
        "text": reply_text,
    })
    save_state()

    target_uid = int(ticket["user_id"])
    reply_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"💬 Ответить в #{tid}", callback_data=f"sup_ureply:{tid}"),
            InlineKeyboardButton(text=f"🔒 Закрыть #{tid}", callback_data=f"sup_uclose:{tid}"),
        ]
    ])
    await safe_send(
        bot,
        target_uid,
        f"💬 <b>Ответ поддержки по тикету <code>#{esc(tid)}</code></b> ({esc(staff['name'])}):\n{esc(reply_text)}",
        reply_markup=reply_kb,
        parse_mode="HTML",
    )

    await safe_answer(
        message,
        f"✅ Ответ по тикету <code>#{esc(tid)}</code> отправлен! Награда хелпера: <b>+{bonus_money} ₽</b>, <b>+{bonus_xp} XP</b>.{promo_note}",
        parse_mode="HTML",
    )


@dp.message(Command("closeticket"))
async def cmd_close_ticket(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_helper(uid, 1):
        await safe_answer(message, "⛔ Закрывать тикеты могут хелперы и администраторы.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/closeticket &lt;ID_тикета&gt;</code>", parse_mode="HTML")
        return

    tid = parts[1].lstrip("#").strip()
    ticket = support_tickets.get(tid)
    if not ticket:
        await safe_answer(message, f"Тикет <code>#{esc(tid)}</code> не найден.", parse_mode="HTML")
        return

    ticket["status"] = "closed"
    target_uid = int(ticket["user_id"])
    u = users.get(str(target_uid))
    if isinstance(u, dict) and u.get("active_ticket") == tid:
        u["active_ticket"] = None
    save_state()

    await safe_send(
        bot,
        target_uid,
        f"🔒 Ваш тикет в поддержку <code>#{esc(tid)}</code> закрыт. Если появятся новые вопросы — напишите <code>/support</code>.",
        parse_mode="HTML",
    )

    await safe_answer(message, f"🔒 Тикет <code>#{esc(tid)}</code> закрыт.", parse_mode="HTML")


@dp.message(Command("info"))
async def cmd_info(message: Message):
    uid = message.from_user.id
    viewer = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) == 1 or not parts[1].strip():
        target = viewer
    else:
        query = parts[1].strip().lstrip("#")
        target = None
        if query.isdigit():
            target = find_player_by_game_id(int(query))
            if target is None and str(query) in users and isinstance(users[str(query)], dict):
                target = normalize_player(users[str(query)], int(query))
        if target is None:
            q_low = query.lower()
            for k, u in users.items():
                if isinstance(u, dict):
                    try:
                        tg_id = int(u.get("tg_id") or k)
                    except ValueError:
                        continue
                    p_norm = normalize_player(u, tg_id)
                    if str(p_norm.get("name", "")).strip().lower() == q_low:
                        target = p_norm
                        break
        if target is None:
            await safe_answer(message, f"❌ Игрок <code>{esc(query)}</code> не найден.", parse_mode="HTML")
            return

    fac_key = target.get("faction", "none")
    if fac_key in FACTIONS:
        fac_name = FACTIONS[fac_key]["name"]
        rk = int(target.get("rank", 1))
        rk_title = get_faction_rank_title(fac_key, rk)
        fac_line = f"🏛 Фракция: <b>{esc(fac_name)}</b> — <b>{esc(rk_title)}</b> (<code>{rk}/13</code>, выговоров: <code>{target.get('f_warns', 0)}/3</code>)"
    else:
        fac_line = "🏛 Фракция: <b>Гражданский</b>"

    age_txt = f"<b>{target['age']} лет</b>" if target.get("age") else "Не указан"
    leader_tag = " 👑 Лидер" if target.get("leader_of") else ""
    a_lvl = get_admin_lvl(int(target["tg_id"]))
    h_lvl = int(target.get("helper_lvl", 0))
    m_lvl = get_media_lvl(int(target["tg_id"]))
    staff_line = ""
    if is_admin(uid, 1) or int(target["tg_id"]) == uid:
        staff_line = (
            f"\n🛡 Админ: <b>{esc(get_admin_title(a_lvl))}</b> | 🛟 Хелпер: <b>{esc(get_helper_title(h_lvl))}</b> (<code>{target.get('helper_answers', 0)}</code> отв.)"
            f"\n🎬 Медиа: <b>{esc(get_media_title(m_lvl))}</b> (призов: <code>{target.get('media_prizes_given', 0)}</code>, промо: <code>{target.get('media_promos_created', 0)}</code>)"
        )

    owned_biz = [b["name"] for b in businesses.values() if isinstance(b, dict) and b.get("owner_uid") == int(target["tg_id"])]
    biz_txt = ", ".join(esc(x) for x in owned_biz) if owned_biz else "Нет"
    cars_txt = ", ".join(esc(SHOP_CARS[c]["name"]) for c in target.get("cars", []) if c in SHOP_CARS) or "Нет"
    houses_txt = ", ".join(esc(SHOP_HOUSES[h]["name"]) for h in target.get("houses", []) if h in SHOP_HOUSES) or "Нет"

    await safe_answer(
        message,
        f"📋 <b>Информация об игроке: {esc(target['name'])}</b> (<code>#{target['game_id']}</code>){leader_tag}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎂 Возраст: {age_txt} | ⭐ Уровень: <b>{target['lvl']}</b> (<code>{target['xp']}</code> XP)\n"
        f"💵 Наличные: <b>{target['money']} ₽</b> | 🏦 Банк: <b>{target['bank']} ₽</b>\n"
        f"❤️ HP: <code>{target['hp']}/100</code> | 🍗 Голод: <code>{target['hunger']}/100</code> | ⚡ Силы: <code>{target['stamina']}/100</code>\n"
        f"🚨 Розыск: <code>{target['wanted']}/6</code> | 🧾 Штрафы: <b>{target['fines']} ₽</b>\n"
        f"{fac_line}\n"
        f"🏢 Бизнес: {biz_txt}\n"
        f"🚗 Авто: {cars_txt}\n"
        f"🏠 Недвижимость: {houses_txt}{staff_line}",
        parse_mode="HTML",
    )


@dp.message(Command("d"))
async def cmd_department_radio(message: Message, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    rk = int(p.get("rank", 1))
    is_adm = is_admin(uid, 1)

    if not is_adm:
        if fid not in FACTIONS or FACTIONS[fid].get("type") == "crime":
            await safe_answer(message, "⛔ Рация департамента (/d) доступна только сотрудникам государственных фракций.")
            return
        if rk < DEP_RADIO_MIN_RANK:
            await safe_answer(
                message,
                f"⛔ Рация департамента доступна с <b>{DEP_RADIO_MIN_RANK} ранга</b> (ваш ранг: <code>{rk}/13</code>).",
                parse_mode="HTML",
            )
            return

    now = time.time()
    mute_until = float(p.get("dep_mute_until", 0.0) or 0.0)
    if mute_until > now and not is_adm:
        await safe_answer(
            message,
            f"🔇 У вас мут рации департамента. Осталось: <b>{esc(format_duration(mute_until - now))}</b>.",
            parse_mode="HTML",
        )
        return

    last_msg = float(p.get("last_dep_msg", 0.0) or 0.0)
    if not is_adm and (now - last_msg) < DEP_RADIO_COOLDOWN:
        await safe_answer(
            message,
            f"⏳ Подождите <b>{int(DEP_RADIO_COOLDOWN - (now - last_msg))} сек.</b> перед следующим сообщением в /d.",
            parse_mode="HTML",
        )
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await safe_answer(
            message,
            "📻 <b>Рация департамента (/d)</b>\n"
            "Формат: <code>/d [Тег] Сообщение</code>\n"
            "Пример: <code>/d [МВД - ФСБ] Требуется подкрепление на выезде.</code>",
            parse_mode="HTML",
        )
        return

    msg_body = parts[1].strip()[:350]
    p["last_dep_msg"] = now
    save_state()

    if fid in FACTIONS:
        rk_title = get_faction_rank_title(fid, rk)
        broadcast = f"📻 <b>[D] [{esc(FACTIONS[fid]['name'])}] {esc(rk_title)} {esc(p['name'])} (<code>#{p['game_id']}</code>):</b> {esc(msg_body)}"
    else:
        broadcast = f"📻 <b>[D] [АДМИНИСТРАЦИЯ] {esc(p['name'])} (<code>#{p['game_id']}</code>):</b> {esc(msg_body)}"

    sent = 0
    for k, u in users.items():
        if not isinstance(u, dict):
            continue
        try:
            t_uid = int(u.get("tg_id") or k)
        except ValueError:
            continue
        u_fac = u.get("faction", "none")
        if (u_fac in FACTIONS and FACTIONS[u_fac].get("type") != "crime") or is_admin(t_uid, 1) or is_helper(t_uid, 1):
            await safe_send(bot, t_uid, broadcast, parse_mode="HTML")
            sent += 1

    await safe_answer(message, f"✅ Сообщение в департамент передано (<code>{sent}</code> адресатам).", parse_mode="HTML")


@dp.message(Command("dmute"))
async def cmd_dmute(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Выдавать мут рации департамента можно со 2 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await safe_answer(message, "Формат: <code>/dmute &lt;игровой_ID&gt; &lt;минуты&gt;</code> (0 — снять мут)", parse_mode="HTML")
        return
    gid = int(parts[1])
    mins = int(parts[2])
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    if mins <= 0:
        target["dep_mute_until"] = 0.0
        save_state()
        await safe_answer(message, f"🔊 Мут рации департамента снят с <b>{esc(target['name'])}</b> (<code>#{gid}</code>).", parse_mode="HTML")
        return
    target["dep_mute_until"] = time.time() + mins * 60
    save_state()
    await safe_answer(message, f"🔇 Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) выдан мут /d на <b>{mins} мин.</b>", parse_mode="HTML")
    await safe_send(bot, int(target["tg_id"]), f"🔇 Вам выдан мут рации департамента (/d) на <b>{mins} мин.</b>", parse_mode="HTML")


@dp.message(Command("start"))
async def cmd_start(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    age_txt = f"{p['age']} лет" if p.get("age") else "Не указан (/setage)"
    await safe_answer(
        message,
        f"🇷🇺 Добро пожаловать в <b>Criminal Russia RP</b>!\n"
        f"Ник: <b>{esc(p['name'])}</b> | Игровой ID: <b><code>#{p['game_id']}</code></b> | Возраст: <b>{esc(age_txt)}</b>\n"
        f"Наличные: <b>{p['money']} ₽</b> | Банк: <b>{p['bank']} ₽</b> | Уровень: <b>{p['lvl']}</b>\n"
        f"❤️ HP: <code>{p['hp']}/100</code> | 🍗 Голод: <code>{p['hunger']}/100</code> | ⚡ Выносливость: <code>{p['stamina']}/100</code>",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


@dp.message(Command("help"))
@dp.message(F.text == "📖 Команды")
async def cmd_help(message: Message):
    uid = message.from_user.id
    lines = [
        "📖 <b>Основные команды и механики:</b>",
        "• <code>/start</code> — запуск и обновление меню",
        "• <code>/setnick &lt;Имя_Фамилия&gt;</code> — сменить RP-ник (20 000 ₽)",
        "• <code>/setage &lt;18..90&gt;</code> — установить игровой возраст персонажа",
        "• <code>/info [ID или Ник]</code> — подробная карточка игрока",
        "• <code>/d &lt;сообщение&gt;</code> — рация департамента (с 6/13 ранга госструктур)",
        "• <code>/pay &lt;ID&gt; &lt;сумма&gt;</code> — перевести деньги игроку (комиссия 3%)",
        "• <code>/bank put &lt;сумма&gt;</code> / <code>/bank take &lt;сумма&gt;</code> — операции с банком",
        "• <code>/work</code> — отработать смену (тратит выносливость и голод)",
        "• <code>/casino &lt;сумма&gt;</code> — сыграть в казино",
        "• <code>/heal</code> — пройти лечение в больнице",
        "• <code>/promo &lt;КОД&gt;</code> — активировать промокод",
        "• <code>/support &lt;текст&gt;</code> — написать в поддержку (или кнопка «🎫 Поддержка»)",
        "• <code>/members [фракция]</code> — состав фракции (13 званий)",
        "• <code>/r &lt;текст&gt;</code>, <code>/fapps</code>, <code>/faccept</code>, <code>/fdecline</code>, <code>/fdeposit</code>, <code>/fwarn</code> — фракции",
        "",
        "🚓 <b>ДПС / ППС / ФСБ / ФСИН / МВД / ВЧ:</b>",
        "• <code>/wanted &lt;ID&gt; &lt;1..6&gt;</code> — выдать розыск",
        "• <code>/clear &lt;ID&gt;</code> — снять розыск",
        "• <code>/fine &lt;ID&gt; &lt;сумма&gt; [причина]</code> — выписать штраф",
        "",
        "🛟 <b>Хелперы и Поддержка:</b>",
        "• <code>/tickets</code> — открытые обращения",
        "• <code>/answer &lt;ID_тикета&gt; &lt;ответ&gt;</code> — ответить игроку в тикете",
        "• <code>/closeticket &lt;ID_тикета&gt;</code> — закрыть обращение",
        "",
        "🎬 <b>Медиа (ранги 1–8):</b>",
        "• <code>/media</code> или кнопка «🎬 Медиа» — панель рангов и лимитов медиа",
        "• <code>/mediaprize &lt;ID&gt; &lt;сумма&gt;</code> — выдать приз игроку (в пределах лимита ранга)",
        "• <code>/announce &lt;текст&gt;</code> — объявление всем игрокам",
        "• <code>/mediasalary</code> — получить медиа-выплату по своему рангу",
        "• <code>/mediastaff</code> — список медиа-состава и рангов",
    ]
    if is_media(uid, 8) or is_admin(uid, 4):
        lines.append("• <code>/setmediarank &lt;ID&gt; &lt;0..8&gt;</code> — назначить ранг медиа (8 ранг медиа / админ 4+)")
    if is_admin(uid, 1):
        lines.extend([
            "",
            "🛡 <b>Администрация (ранги 1–8):</b>",
            "• <code>/admins</code> — список администрации и ранги 1–8",
            "• <code>/players</code> — список игроков",
            "• <code>/changename &lt;ID&gt; &lt;Имя_Фамилия&gt;</code> — сменить ник игроку",
            "• <code>/addpromo &lt;КОД&gt; &lt;сумма&gt; &lt;активаций&gt;</code> — создать промокод",
            "• <code>/delpromo &lt;КОД&gt;</code> — удалить промокод",
            "• <code>/sethelper &lt;ID&gt; &lt;0..8&gt;</code> и <code>/helpers</code> — ранги хелперов (1–8)",
            "• <code>/setmedia &lt;ID&gt; &lt;0..8&gt;</code> — выдать или изменить ранг медиа (0 — снять)",
            "• <code>/setadmin &lt;ID&gt; &lt;0..8&gt;</code> — выдать уровень админа",
            "• <code>/setleader &lt;ID&gt; &lt;фракция|none&gt;</code> — назначить лидера",
            "• <code>/dmute &lt;ID&gt; &lt;минуты&gt;</code> — мут рации департамента",
            "• <code>/ban &lt;ID&gt; [причина]</code> и <code>/unban &lt;ID&gt;</code>",
            "• <code>/tempban &lt;ID&gt; &lt;срок&gt; [причина]</code> и <code>/untempban &lt;ID&gt;</code>",
            "• <code>/resetplayer &lt;ID&gt;</code> и <code>/wipeall CONFIRM</code>",
        ])
    await safe_answer(message, "\n".join(lines), reply_markup=main_kb(uid), parse_mode="HTML")


@dp.message(F.text == "👤 Профиль")
async def btn_profile(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fac_key = p.get("faction", "none")
    if fac_key in FACTIONS:
        fac_name = FACTIONS[fac_key]["name"]
        rk_title = get_faction_rank_title(fac_key, int(p["rank"]))
        warns_txt = f" | Выговоров: <code>{p.get('f_warns', 0)}/3</code>" if int(p.get("f_warns", 0)) > 0 else ""
        fac_line = f"🏛 Фракция: <b>{esc(fac_name)}</b> — <b>{esc(rk_title)}</b> (<code>{p['rank']}/13</code>, очки: <code>{p['faction_points']}</code>{warns_txt})"
    else:
        fac_line = "🏛 Фракция: <b>Гражданский</b>"
    role_tag = " 👑 Лидер" if p.get("leader_of") else ""
    a_lvl = get_admin_lvl(uid)
    admin_line = f"\n🛡 Администрация: <b>{esc(get_admin_title(a_lvl))}</b>" if is_creator(uid) or a_lvl > 0 else ""
    h_lvl = int(p.get("helper_lvl", 0))
    helper_line = f"\n🛟 Хелперка: <b>{esc(get_helper_title(h_lvl))}</b> (ответов: <code>{p['helper_answers']}</code>)" if h_lvl > 0 else ""
    m_lvl = get_media_lvl(uid)
    media_line = f"\n🎬 Медиа: <b>{esc(get_media_title(m_lvl))}</b>" if m_lvl > 0 else ""
    cars_txt = ", ".join(esc(SHOP_CARS[c]["name"]) for c in p["cars"] if c in SHOP_CARS) or "Нет"
    houses_txt = ", ".join(esc(SHOP_HOUSES[h]["name"]) for h in p["houses"] if h in SHOP_HOUSES) or "Нет"
    age_txt = f"<b>{p['age']} лет</b>" if p.get("age") else "Не указан (/setage)"

    await safe_answer(
        message,
        f"👤 <b>Профиль: {esc(p['name'])}</b> (<code>#{p['game_id']}</code>)\n"
        f"🎂 Игровой возраст: {age_txt}\n"
        f"⭐ Уровень: <b>{p['lvl']}</b> (опыт: <code>{p['xp']}</code>)\n"
        f"💵 Наличные: <b>{p['money']} ₽</b> | 🏦 Банк: <b>{p['bank']} ₽</b>\n"
        f"❤️ Здоровье: <code>{p['hp']}/100</code> | 🍗 Голод: <code>{p['hunger']}/100</code> | ⚡ Выносливость: <code>{p['stamina']}/100</code>\n"
        f"🎰 Казино: побед <code>{p['casino_wins']}</code> / поражений <code>{p['casino_losses']}</code>\n"
        f"🚨 Розыск: <code>{p['wanted']}/6</code> | 🧾 Штрафы: <b>{p['fines']} ₽</b>\n"
        f"{fac_line}{role_tag}{admin_line}{helper_line}{media_line}\n"
        f"🚗 Авто: {cars_txt}\n"
        f"🏠 Недвижимость: {houses_txt}",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


@dp.message(Command("setnick"))
async def cmd_setnick(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await safe_answer(
            message,
            f"🪪 <b>Смена игрового ника</b>\n"
            f"Текущий ник: <b>{esc(p['name'])}</b>\n"
            f"Стоимость смены: <b>{NICK_CHANGE_COST} ₽</b> (наличными)\n"
            f"Формат: <code>/setnick Имя_Фамилия</code>",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return

    now = time.time()
    last_change = float(p.get("last_nick_change", 0.0) or 0.0)
    left = int(NICK_CHANGE_COOLDOWN - (now - last_change))
    if left > 0 and not is_admin(uid, 1):
        await safe_answer(
            message,
            f"⏳ Менять ник можно раз в час. Подождите <b>{esc(format_duration(left))}</b>.",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return

    ok, res = validate_rp_nick(parts[1])
    if not ok:
        await safe_answer(message, f"⚠️ {res}", reply_markup=main_kb(uid), parse_mode="HTML")
        return

    new_nick = res
    if new_nick.lower() == str(p.get("name", "")).lower():
        await safe_answer(message, "Этот ник уже установлен у вас.", reply_markup=main_kb(uid))
        return

    if is_nick_taken(new_nick, exclude_tg_id=uid):
        await safe_answer(message, f"❌ Ник <code>{esc(new_nick)}</code> уже занят другим игроком.", reply_markup=main_kb(uid), parse_mode="HTML")
        return

    if int(p.get("money", 0)) < NICK_CHANGE_COST:
        await safe_answer(
            message,
            f"💸 Недостаточно наличных для смены ника. Нужно <b>{NICK_CHANGE_COST} ₽</b>.",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return

    old_nick = p["name"]
    p["money"] = int(p["money"]) - NICK_CHANGE_COST
    p["name"] = new_nick
    p["last_nick_change"] = now
    save_state()

    await safe_answer(
        message,
        f"✅ Игровой ник изменён: <b>{esc(old_nick)}</b> ➔ <b>{esc(new_nick)}</b> (-{NICK_CHANGE_COST} ₽).",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


@dp.message(Command("changename"))
async def cmd_changename(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 3):
        await safe_answer(message, "⛔ Принудительно менять ники игрокам можно с 3 ранга администратора.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/changename &lt;игровой_ID&gt; &lt;Имя_Фамилия&gt;</code>", parse_mode="HTML")
        return

    gid = int(parts[1])
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return

    ok, res = validate_rp_nick(parts[2])
    if not ok:
        await safe_answer(message, f"⚠️ {res}", parse_mode="HTML")
        return

    new_nick = res
    target_tg_id = int(target["tg_id"])
    if is_nick_taken(new_nick, exclude_tg_id=target_tg_id):
        await safe_answer(message, f"❌ Ник <code>{esc(new_nick)}</code> уже занят.", parse_mode="HTML")
        return

    old_nick = target["name"]
    target["name"] = new_nick
    save_state()

    await safe_answer(
        message,
        f"🪪 Администратор сменил ник игрока <code>#{gid}</code>: <b>{esc(old_nick)}</b> ➔ <b>{esc(new_nick)}</b>.",
        parse_mode="HTML",
    )
    await safe_send(
        bot,
        target_tg_id,
        f"🪪 Администрация изменила ваш игровой ник на <b>{esc(new_nick)}</b>.",
        parse_mode="HTML",
    )


@dp.message(Command("setage"))
async def cmd_setage(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)

    parts = (message.text or "").split()
    if len(parts) != 2:
        cur_age = f"<b>{p['age']} лет</b>" if p.get("age") else "не установлен"
        await safe_answer(
            message,
            f"🎂 <b>Игровой возраст персонажа</b>\n"
            f"Текущий возраст: {cur_age}\n"
            f"Установить возраст (от <code>18</code> до <code>90</code> лет): <code>/setage &lt;возраст&gt;</code>",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return

    try:
        age_val = int(parts[1])
    except ValueError:
        await safe_answer(message, "Возраст должен быть числом (например, <code>/setage 24</code>).", parse_mode="HTML")
        return

    if not (18 <= age_val <= 90):
        await safe_answer(message, "⚠️ Игровой возраст персонажа должен быть от <b>18</b> до <b>90</b> лет.", parse_mode="HTML")
        return

    p["age"] = age_val
    save_state()
    await safe_answer(
        message,
        f"✅ В паспорте персонажа установлен игровой возраст: <b>{age_val} лет</b>.",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


@dp.message(Command("pay"))
async def cmd_pay(message: Message, bot: Bot):
    uid = message.from_user.id
    sender = get_player(uid, message.from_user.full_name)

    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(
            message,
            f"💸 <b>Перевод игроку</b>\n"
            f"Формат: <code>/pay &lt;игровой_ID&gt; &lt;сумма&gt;</code>\n"
            f"Лимиты: от <code>{PAY_MIN_AMOUNT}</code> до <code>{PAY_MAX_AMOUNT}</code> ₽ (комиссия <code>{int(PAY_COMMISSION_RATE * 100)}%</code>).",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return

    try:
        target_gid = int(parts[1].lstrip("#"))
        amount = int(parts[2])
    except ValueError:
        await safe_answer(message, "Игровой ID и сумма перевода должны быть числами.")
        return

    if target_gid == int(sender["game_id"]):
        await safe_answer(message, "Нельзя перевести деньги самому себе.")
        return

    if not (PAY_MIN_AMOUNT <= amount <= PAY_MAX_AMOUNT):
        await safe_answer(
            message,
            f"⚠️ Сумма перевода должна быть от <b>{PAY_MIN_AMOUNT} ₽</b> до <b>{PAY_MAX_AMOUNT} ₽</b>.",
            parse_mode="HTML",
        )
        return

    target = find_player_by_game_id(target_gid)
    if not target:
        await safe_answer(message, f"Игрок с ID <code>#{target_gid}</code> не найден.", parse_mode="HTML")
        return

    commission = max(1, int(round(amount * PAY_COMMISSION_RATE)))
    total_cost = amount + commission

    if int(sender["money"]) < total_cost:
        await safe_answer(
            message,
            f"💸 Недостаточно наличных! С учётом комиссии <code>{int(PAY_COMMISSION_RATE * 100)}%</code> (<code>{commission} ₽</code>) нужно <b>{total_cost} ₽</b>, у вас <b>{sender['money']} ₽</b>.",
            parse_mode="HTML",
        )
        return

    sender["money"] = int(sender["money"]) - total_cost
    target["money"] = int(target["money"]) + amount
    save_state()

    await safe_answer(
        message,
        f"✅ Перевод выполнен!\n"
        f"Получатель: <b>{esc(target['name'])}</b> (<code>#{target_gid}</code>)\n"
        f"Сумма: <b>{amount} ₽</b> (комиссия: <code>{commission} ₽</code>, списано: <b>{total_cost} ₽</b>)\n"
        f"Остаток наличных: <b>{sender['money']} ₽</b>",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )
    await safe_send(
        bot,
        int(target["tg_id"]),
        f"💵 Игрок <b>{esc(sender['name'])}</b> (<code>#{sender['game_id']}</code>) перевёл вам <b>+{amount} ₽</b>!",
        parse_mode="HTML",
    )


@dp.message(Command("work"))
@dp.message(F.text == "💵 Работа")
async def cmd_work(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)

    if int(p.get("hp", 100)) <= 10:
        await safe_answer(message, "🏥 Вы слишком ослабли для работы! Загляните в <b>«🏥 Больница»</b> (<code>/heal</code>).", parse_mode="HTML")
        return
    if int(p.get("hunger", 100)) < 15:
        await safe_answer(message, "🍗 Вы слишком голодны для смены (голод <code>&lt; 15</code>). Перекусите в <b>«🍔 Еда и отдых»</b>.", parse_mode="HTML")
        return
    if int(p.get("stamina", 100)) < 20:
        await safe_answer(message, "⚡ Не хватает выносливости (нужно минимум <code>20</code>). Восстановите силы в <b>«🍔 Еда и отдых»</b>.", parse_mode="HTML")
        return

    now = time.time()
    cooldown = 30
    left = int(cooldown - (now - float(p.get("last_work", 0.0))))
    if left > 0:
        await safe_answer(message, f"⏳ Отдохните ещё <b>{left} сек.</b> перед следующей сменой.", parse_mode="HTML")
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
    while p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()

    await safe_answer(
        message,
        f"💼 Смена завершена! Вы заработали <b>+{reward} ₽</b> и <b>+25 XP</b>.\n"
        f"Наличные: <b>{p['money']} ₽</b> | Уровень: <b>{p['lvl']}</b>\n"
        f"🍗 Голод: <code>{p['hunger']}/100</code> | ⚡ Выносливость: <code>{p['stamina']}/100</code>",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


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
        f"🍔 <b>Питание и восстановление сил</b>\n"
        f"❤️ HP: <code>{p['hp']}/100</code> | 🍗 Голод: <code>{p['hunger']}/100</code> | ⚡ Выносливость: <code>{p['stamina']}/100</code>\n"
        f"Наличные: <b>{p['money']} ₽</b>",
        reply_markup=render_food_kb(),
        parse_mode="HTML",
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
            f"✅ Вы воспользовались пунктом <b>«{esc(item['name'])}»</b> (-{price} ₽).\n"
            f"❤️ HP: <code>{p['hp']}/100</code> | 🍗 Голод: <code>{p['hunger']}/100</code> | ⚡ Выносливость: <code>{p['stamina']}/100</code>",
            parse_mode="HTML",
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
        return False, f"Недостаточно наличных на лечение (нужно <b>{cost} ₽</b>)."

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
        return True, f"💉 Полный курс лечения пройден (-{cost} ₽)! Восстановлены <b>100 HP</b>, <b>100 голода</b> и <b>100 выносливости</b>."
    return True, f"🩺 Лечение успешно завершено (-{cost} ₽)! Здоровье восстановлено до <b>100 HP</b>."


@dp.message(Command("heal"))
@dp.message(F.text == "🏥 Больница")
async def cmd_hospital(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await safe_answer(
        message,
        f"🏥 <b>Областная больница (Минздрав)</b>\n"
        f"Ваше здоровье: <code>{p['hp']}/100 HP</code> | Голод: <code>{p['hunger']}/100</code> | Выносливость: <code>{p['stamina']}/100</code>\n"
        f"Наличные: <b>{p['money']} ₽</b>\n\n"
        f"Выберите курс лечения или используйте <code>/heal</code>:",
        reply_markup=render_hospital_kb(),
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("hosp:"))
async def cb_hospital(callback: CallbackQuery):
    mode = callback.data.split(":", 1)[1]
    ok, msg_txt = await perform_hospital_treatment(callback.from_user.id, callback.from_user.full_name, mode)
    plain_alert = re.sub(r"<[^>]+>", "", msg_txt)
    await callback.answer(plain_alert, show_alert=True)
    if ok and callback.message:
        await callback.message.answer(msg_txt, parse_mode="HTML")


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
        return False, "🎰 Минимальная ставка в казино — <b>100 ₽</b>."
    if bet > 10_000_000:
        return False, "🎰 Максимальная ставка за один раунд — <b>10 000 000 ₽</b>."
    if int(p["money"]) < bet:
        return False, f"💸 Недостаточно наличных! У вас <b>{p['money']} ₽</b>."

    roll = random.randint(1, 100)
    if mode == "risk":
        if roll >= 82:
            payout = bet * 5
            profit = payout - bet
            p["money"] += profit
            p["casino_wins"] = int(p.get("casino_wins", 0)) + 1
            save_state()
            return True, f"🔥 <b>РИСК-ДЖЕКПОТ (<code>{roll}/100</code>)!</b> Выигрыш <b>{payout} ₽</b> (чистыми <b>+{profit} ₽</b>). Баланс: <b>{p['money']} ₽</b>."
        p["money"] -= bet
        p["casino_losses"] = int(p.get("casino_losses", 0)) + 1
        save_state()
        return True, f"📉 Не повезло в риск-игре (<code>{roll}/100</code>). Потеряно <b>-{bet} ₽</b>. Баланс: <b>{p['money']} ₽</b>."

    if roll >= 92:
        payout = int(bet * 3.5)
        profit = payout - bet
        p["money"] += profit
        p["casino_wins"] = int(p.get("casino_wins", 0)) + 1
        save_state()
        return True, f"💎 <b>КРУПНЫЙ ВЫИГРЫШ (<code>{roll}/100</code>, x3.5)!</b> Выплата <b>{payout} ₽</b> (чистыми <b>+{profit} ₽</b>). Баланс: <b>{p['money']} ₽</b>."
    if roll >= 53:
        payout = int(bet * 2.0)
        profit = payout - bet
        p["money"] += profit
        p["casino_wins"] = int(p.get("casino_wins", 0)) + 1
        save_state()
        return True, f"🎲 <b>ПОБЕДА (<code>{roll}/100</code>, x2.0)!</b> Выплата <b>{payout} ₽</b> (чистыми <b>+{profit} ₽</b>). Баланс: <b>{p['money']} ₽</b>."

    p["money"] -= bet
    p["casino_losses"] = int(p.get("casino_losses", 0)) + 1
    save_state()
    return True, f"📉 Проигрыш (<code>{roll}/100</code>). Ставка <b>{bet} ₽</b> сгорела. Баланс: <b>{p['money']} ₽</b>."


@dp.message(F.text == "🎰 Казино")
async def btn_casino(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    await safe_answer(
        message,
        f"🎰 <b>Казино «Imperial»</b>\n"
        f"Наличные: <b>{p['money']} ₽</b> | Побед: <code>{p['casino_wins']}</code> / Поражений: <code>{p['casino_losses']}</code>\n\n"
        f"• <b>Обычная игра</b>: шанс победы ~48% (x2.0 / x3.5)\n"
        f"• <b>Риск x5</b>: шанс победы ~19% (x5.0)\n"
        f"Выберите кнопку или введите <code>/casino &lt;сумма&gt;</code>:",
        reply_markup=render_casino_kb(),
        parse_mode="HTML",
    )


@dp.message(Command("casino"))
async def cmd_casino(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/casino &lt;сумма&gt;</code> (например, <code>/casino 10000</code>)", parse_mode="HTML")
        return
    _, text = run_casino_round(p, int(parts[1]), mode="std")
    await safe_answer(message, text, parse_mode="HTML")


@dp.callback_query(F.data.startswith("cas:"))
async def cb_casino(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    _, mode, amt_s = callback.data.split(":", 2)
    _, text = run_casino_round(p, int(amt_s), mode=mode)
    await callback.answer("Ставка сыграна!")
    if callback.message:
        await callback.message.answer(text, parse_mode="HTML")


@dp.message(Command("addpromo"))
async def cmd_addpromo(message: Message):
    uid = message.from_user.id
    spec = get_media_spec(uid)
    if not (is_admin(uid, 3) or spec is not None):
        await safe_answer(message, "⛔ Создавать промокоды можно с 3 ранга администратора или с ролью медиа.")
        return

    parts = (message.text or "").split()
    if len(parts) not in (4, 5):
        await safe_answer(
            message,
            "Формат: <code>/addpromo &lt;КОД&gt; &lt;сумма&gt; &lt;активаций&gt;</code> или <code>/addpromo &lt;КОД&gt; &lt;сумма&gt; &lt;xp&gt; &lt;активаций&gt;</code>",
            parse_mode="HTML",
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

    max_money = 500_000
    max_uses = 100_000
    if not is_admin(uid, 3) and spec is not None:
        max_money = int(spec["max_promo_money"])
        max_uses = int(spec["max_promo_uses"])

    if not (0 <= amount <= max_money) or not (0 <= xp_bonus <= 5000) or not (1 <= uses <= max_uses):
        await safe_answer(
            message,
            f"Лимиты для вашего статуса: сумма <code>0..{max_money} ₽</code>, XP <code>0..5 000</code>, активаций <code>1..{max_uses}</code>.",
            parse_mode="HTML",
        )
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
        "creator_id": uid,
    }
    p = get_player(uid, message.from_user.full_name)
    if spec is not None:
        p["media_promos_created"] = int(p.get("media_promos_created", 0)) + 1
    save_state()
    await safe_answer(
        message,
        f"🎟 Промокод <b><code>{esc(code)}</code></b> создан!\n"
        f"💵 Деньги: <b>{amount} ₽</b> | ⭐ XP: <b>{xp_bonus}</b> | Активаций: <b>{uses}</b>",
        parse_mode="HTML",
    )


@dp.message(Command("delpromo"))
async def cmd_delpromo(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 3):
        await safe_answer(message, "⛔ Удалять промокоды можно с 3 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/delpromo &lt;КОД&gt;</code>", parse_mode="HTML")
        return
    code = parts[1].strip().upper()
    if code not in promocodes:
        await safe_answer(message, "Промокод не найден.")
        return
    del promocodes[code]
    save_state()
    await safe_answer(message, f"🗑 Промокод <b><code>{esc(code)}</code></b> удалён.", parse_mode="HTML")


@dp.message(Command("promo"))
async def cmd_promo(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/promo &lt;КОД&gt;</code>", parse_mode="HTML")
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
        f"🎉 Промокод <b><code>{esc(code)}</code></b> активирован!\n"
        f"Награда: <b>+{money_rew} ₽</b>, <b>+{xp_rew} XP</b>.",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


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
            await safe_answer(message, "Вы не состоите во фракции. Укажите ключ: <code>/members &lt;фракция&gt;</code>", parse_mode="HTML")
            return

    if fid not in FACTIONS:
        keys_str = ", ".join(f"<code>{esc(k)}</code>" for k in FACTIONS)
        await safe_answer(message, f"Неизвестная фракция. Доступные ключи: {keys_str}", parse_mode="HTML")
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
            r_val = 13 if u.get("leader_of") == fid else int(u.get("rank", 1))
            roster.append((r_val, str(u.get("name", "Игрок")), int(u.get("game_id", 0)), int(u.get("wanted", 0)), int(u.get("f_warns", 0))))

    roster.sort(key=lambda item: (-item[0], item[1].lower()))
    fac_name = FACTIONS[fid]["name"]

    if not roster:
        await safe_answer(message, f"👥 В фракции <b>{esc(fac_name)}</b> сейчас никого нет.", parse_mode="HTML")
        return

    lines = [f"👥 <b>Состав фракции «{esc(fac_name)}»</b> (<code>{len(roster)}</code> чел.):\n"]
    for idx, (r_val, uname, gid, w_lvl, fw) in enumerate(roster, start=1):
        leader_tag = " 👑 Лидер" if r_val == 13 else ""
        wanted_tag = f" 🚨<code>{w_lvl}</code>" if w_lvl > 0 else ""
        warn_tag = f" ⚠️<code>{fw}/3</code>" if fw > 0 else ""
        lines.append(f"{idx}. <b>{esc(uname)}</b> (<code>#{gid}</code>) — {esc(get_faction_rank_title(fid, r_val))} (<code>{r_val}/13</code>){leader_tag}{wanted_tag}{warn_tag}")

    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


@dp.message(Command("wanted"))
async def cmd_wanted(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Команда доступна сотрудникам МВД / ДПС / ППС / ФСБ / ФСИН / ВЧ и администрации.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: <code>/wanted &lt;игровой_ID&gt; &lt;уровень_1..6&gt;</code>", parse_mode="HTML")
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
        await safe_answer(message, f"Игрок с ID <code>#{target_gid}</code> не найден.", parse_mode="HTML")
        return

    target["wanted"] = stars
    save_state()
    await safe_answer(
        message,
        f"🚨 Игроку <b>{esc(target['name'])}</b> (<code>#{target_gid}</code>) выдан розыск: <b><code>{stars}/6</code></b>.",
        parse_mode="HTML",
    )


@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Команда доступна сотрудникам МВД / ДПС / ППС / ФСБ / ФСИН / ВЧ и администрации.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/clear &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return

    try:
        target_gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return

    target = find_player_by_game_id(target_gid)
    if not target:
        await safe_answer(message, f"Игрок с ID <code>#{target_gid}</code> не найден.", parse_mode="HTML")
        return

    target["wanted"] = 0
    save_state()
    await safe_answer(message, f"✅ С игрока <b>{esc(target['name'])}</b> (<code>#{target_gid}</code>) снят розыск.", parse_mode="HTML")


@dp.message(Command("fine"))
async def cmd_fine(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    if not is_police_faction(actor):
        await safe_answer(message, "⛔ Выписывать штрафы могут сотрудники МВД / ДПС / ППС / ФСБ / ФСИН / ВЧ и администрация.")
        return

    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 3:
        await safe_answer(message, "Формат: <code>/fine &lt;игровой_ID&gt; &lt;сумма&gt; [причина]</code>", parse_mode="HTML")
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
        await safe_answer(message, f"Игрок с ID <code>#{target_gid}</code> не найден.", parse_mode="HTML")
        return

    if target["money"] >= amount:
        target["money"] -= amount
        paid_msg = f"списано <b>{amount} ₽</b> наличными"
    elif target["bank"] >= amount:
        target["bank"] -= amount
        paid_msg = f"списано <b>{amount} ₽</b> с банковского счёта"
    else:
        target["fines"] = int(target.get("fines", 0)) + amount
        paid_msg = f"добавлено в неоплаченные штрафы (<b>+{amount} ₽</b>)"

    actor["money"] += max(100, int(amount * 0.2))
    save_state()

    await safe_answer(
        message,
        f"🧾 Выписан штраф игроку <b>{esc(target['name'])}</b> (<code>#{target_gid}</code>) на <b>{amount} ₽</b> ({paid_msg}).\n"
        f"Причина: <i>{esc(reason)}</i>",
        parse_mode="HTML",
    )


@dp.message(F.text == "🏢 Бизнесы")
async def btn_biz(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    await render_biz_menu(message, uid, edit=False)


async def render_biz_menu(target_msg: Message, uid: int, edit: bool = False):
    now = time.time()
    lines = ["🏢 <b>Бизнесы Criminal Russia:</b>\n"]
    kb_rows: list[list[InlineKeyboardButton]] = []

    for bid, b in businesses.items():
        income_hr = int(b.get("income_per_hour", 0))
        owner_uid = b.get("owner_uid")
        if owner_uid == uid:
            last_col = float(b.get("last_collect", 0.0))
            elapsed_hr = max(0.0, (now - last_col) / 3600.0) if last_col > 0 else 0.0
            pending = int(b.get("cash", 0)) + int(elapsed_hr * income_hr)
            lines.append(
                f"• <b>{esc(b['name'])}</b> <i>(Ваш бизнес)</i> — доход <code>{income_hr} ₽/ч</code>, к сбору: <b>{pending} ₽</b>"
            )
            refund = int(int(b["price"]) * 0.7)
            kb_rows.append([
                InlineKeyboardButton(text=f"💰 Собрать ({pending} ₽)", callback_data=f"biz_take:{bid}"),
                InlineKeyboardButton(text=f"🏷 Продать ({refund} ₽)", callback_data=f"biz_sell:{bid}"),
            ])
        elif owner_uid is None:
            lines.append(f"• <b>{esc(b['name'])}</b> — цена <b>{b['price']} ₽</b>, доход <code>{income_hr} ₽/ч</code> <i>(Свободен)</i>")
            kb_rows.append([
                InlineKeyboardButton(text=f"🛒 Купить {b['name']}", callback_data=f"biz_buy:{bid}")
            ])
        else:
            lines.append(
                f"• <b>{esc(b['name'])}</b> — владелец: <b>{esc(b.get('owner_name') or 'Игрок')}</b>, доход <code>{income_hr} ₽/ч</code>"
            )

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows) if kb_rows else None
    text = "\n".join(lines)
    if edit:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="HTML")


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


@dp.message(Command("mediaprize"))
async def cmd_mediaprize(message: Message, bot: Bot):
    uid = message.from_user.id
    spec = get_media_spec(uid)
    if spec is None:
        await safe_answer(message, "⛔ Команда доступна только медиа-партнёрам (ранги 1–8).")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(
            message,
            f"Формат: <code>/mediaprize &lt;игровой_ID&gt; &lt;сумма&gt;</code>\nВаш лимит по рангу: до <b>{spec['max_prize']} ₽</b>.",
            parse_mode="HTML",
        )
        return
    try:
        gid = int(parts[1].lstrip("#"))
        amount = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и сумма должны быть числами.")
        return
    max_prize = int(spec["max_prize"])
    if not (1 <= amount <= max_prize):
        await safe_answer(
            message,
            f"Сумма медиа-приза для вашего ранга (<b>{esc(get_media_title(int(spec['lvl'])))}</b>) должна быть от <code>1</code> до <b>{max_prize} ₽</b>.",
            parse_mode="HTML",
        )
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    actor = get_player(uid, message.from_user.full_name)
    target["money"] += amount
    actor["media_prizes_given"] = int(actor.get("media_prizes_given", 0)) + 1
    save_state()
    await safe_answer(
        message,
        f"🎬 Выдан медиа-приз <b>+{amount} ₽</b> игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>).",
        parse_mode="HTML",
    )
    await safe_send(
        bot,
        int(target["tg_id"]),
        f"🎬 Вы получили медиа-приз <b>+{amount} ₽</b> от <b>{esc(actor['name'])}</b>!",
        parse_mode="HTML",
    )


@dp.message(Command("announce"))
async def cmd_announce(message: Message, bot: Bot):
    uid = message.from_user.id
    spec = get_media_spec(uid)
    adm = is_admin(uid, 1)
    if not (adm or spec is not None):
        await safe_answer(message, "⛔ Команда доступна медиа и администрации.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await safe_answer(message, "Формат: <code>/announce &lt;текст&gt;</code>", parse_mode="HTML")
        return

    actor = get_player(uid, message.from_user.full_name)
    now = time.time()
    if not adm and spec is not None:
        cd = int(spec["announce_cd"])
        last_ann = float(actor.get("last_media_announce", 0.0) or 0.0)
        left = int(cd - (now - last_ann))
        if left > 0:
            await safe_answer(
                message,
                f"⏳ Кулдаун медиа-объявления для вашего ранга: подождите <b>{esc(format_duration(left))}</b>.",
                parse_mode="HTML",
            )
            return
        actor["last_media_announce"] = now

    if adm:
        header = "📢 <b>ОБЪЯВЛЕНИЕ АДМИНИСТРАЦИИ</b>"
    else:
        m_title = get_media_title(int(spec["lvl"]))
        header = f"🎬 <b>МЕДИА-ОБЪЯВЛЕНИЕ</b> <i>({esc(m_title)} — {esc(actor['name'])})</i>"

    body = f"{header}\n\n{esc(parts[1].strip())}"
    save_state()
    sent = 0
    for k in list(users.keys()):
        try:
            await safe_send(bot, int(k), body, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    await safe_answer(message, f"✅ Объявление отправлено <code>{sent}</code> игрокам.", parse_mode="HTML")


@dp.message(Command("mediasalary"))
async def cmd_mediasalary(message: Message):
    uid = message.from_user.id
    spec = get_media_spec(uid)
    if spec is None:
        await safe_answer(message, "⛔ Команда доступна только медиа-партнёрам (ранги 1–8).")
        return
    p = get_player(uid, message.from_user.full_name)
    now = time.time()
    cd = 3600
    last_sal = float(p.get("last_media_salary", 0.0) or 0.0)
    left = int(cd - (now - last_sal))
    if left > 0 and not is_creator(uid):
        await safe_answer(
            message,
            f"⏳ Медиа-выплата доступна раз в час. Подождите <b>{esc(format_duration(left))}</b>.",
            parse_mode="HTML",
        )
        return
    bonus = int(spec["salary_bonus"])
    p["money"] += bonus
    p["last_media_salary"] = now
    save_state()
    await safe_answer(
        message,
        f"🎬 Выплата медиа (<b>{esc(get_media_title(int(spec['lvl'])))}</b>): получено <b>+{bonus} ₽</b>!",
        parse_mode="HTML",
    )


@dp.message(Command("mediastaff"))
async def cmd_mediastaff(message: Message):
    uid = message.from_user.id
    if not (is_media(uid, 1) or is_admin(uid, 1)):
        await safe_answer(message, "⛔ Список медиа-состава доступен медиа-партнёрам и администрации.")
        return
    staff = []
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            normalize_player(u, tg_id)
            ml = get_media_lvl(tg_id)
            if ml > 0:
                staff.append((ml, str(u["name"]), int(u["game_id"]), int(u.get("media_prizes_given", 0)), int(u.get("media_promos_created", 0))))
    staff.sort(key=lambda x: (-x[0], x[1].lower()))
    lines = [f"🎬 <b>Медиа-состав проекта</b> (<code>{len(staff)}</code> чел.):\n"]
    if not staff:
        lines.append("Активных медиа-партнёров пока нет.")
    else:
        for idx, (ml, nm, gid, pr_cnt, pm_cnt) in enumerate(staff, start=1):
            lines.append(
                f"{idx}. <b>{esc(nm)}</b> (<code>#{gid}</code>) — <b>{esc(get_media_title(ml))}</b> | призов: <code>{pr_cnt}</code>, промо: <code>{pm_cnt}</code>"
            )
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


def render_media_ranks_table() -> str:
    rows = []
    for r_idx in sorted(MEDIA_RANKS.keys()):
        info = MEDIA_RANKS[r_idx]
        rows.append(
            f"• <code>{r_idx}</code> — <b>{esc(info['title'])}</b>: приз до <b>{info['max_prize']} ₽</b>, "
            f"промо до <b>{info['max_promo_money']} ₽</b> (<code>{info['max_promo_uses']}</code> акт.), "
            f"выплата <b>+{info['salary_bonus']} ₽/ч</b>"
        )
    return "\n".join(rows)


@dp.message(Command("setmediarank"))
async def cmd_setmediarank(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    actor_m_lvl = get_media_lvl(uid)
    can_manage = is_admin(uid, 4) or (actor_m_lvl >= 8)
    if not can_manage:
        await safe_answer(message, "⛔ Назначать ранги медиа могут админы 4+ ранга или Руководитель медиа-отдела (8 ранг).")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(
            message,
            f"Формат: <code>/setmediarank &lt;игровой_ID&gt; &lt;0..8&gt;</code>\n\n<b>Ранги медиа:</b>\n{render_media_ranks_table()}",
            parse_mode="HTML",
        )
        return

    try:
        gid = int(parts[1].lstrip("#"))
        lvl = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и ранг должны быть числами.")
        return

    if not (0 <= lvl <= MEDIA_MAX_RANK):
        await safe_answer(message, f"Ранг медиа должен быть от <code>0</code> до <code>{MEDIA_MAX_RANK}</code>.", parse_mode="HTML")
        return

    if not is_admin(uid, 4) and lvl >= actor_m_lvl:
        await safe_answer(message, "⛔ Вы не можете выдать ранг медиа равный или выше своего.")
        return

    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return

    target["media_lvl"] = lvl
    target["is_media"] = bool(lvl > 0)
    save_state()

    title_str = get_media_title(lvl)
    await safe_answer(
        message,
        f"🎬 Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) установлен статус медиа: <b>{esc(title_str)}</b>.",
        parse_mode="HTML",
    )
    if lvl > 0:
        await safe_send(bot, int(target["tg_id"]), f"🎬 Вам назначен статус медиа: <b>{esc(title_str)}</b>!", parse_mode="HTML")
    else:
        await safe_send(bot, int(target["tg_id"]), "🎬 Ваш статус медиа был снят.", parse_mode="HTML")


@dp.message(Command("media"))
@dp.message(F.text == "🎬 Медиа")
async def cmd_media_panel(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    spec = get_media_spec(uid)
    if spec is None:
        await safe_answer(
            message,
            "⛔ Раздел доступен только медиа-партнёрам (выдача через <code>/setmedia &lt;ID&gt; &lt;1..8&gt;</code>).",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return
    m_lvl = int(spec["lvl"])
    manage_hint = "\n• <code>/setmediarank &lt;ID&gt; &lt;0..8&gt;</code> — назначение рангов медиа" if (is_admin(uid, 4) or m_lvl >= 8) else ""
    await safe_answer(
        message,
        f"🎬 <b>Меню Медиа-партнёра</b>\n"
        f"Ваш ранг: <b>{esc(get_media_title(m_lvl))}</b>\n"
        f"• Лимит приза: до <b>{spec['max_prize']} ₽</b> (<code>/mediaprize &lt;ID&gt; &lt;сумма&gt;</code>)\n"
        f"• Лимит промокода: до <b>{spec['max_promo_money']} ₽</b>, до <code>{spec['max_promo_uses']}</code> акт. (<code>/addpromo</code>)\n"
        f"• Кулдаун объявления: <code>{spec['announce_cd']} сек.</code> (<code>/announce &lt;текст&gt;</code>)\n"
        f"• Часовая выплата: <b>+{spec['salary_bonus']} ₽</b> (<code>/mediasalary</code>)\n"
        f"• Статистика: выдано призов <code>{p.get('media_prizes_given', 0)}</code>, создано промокодов <code>{p.get('media_promos_created', 0)}</code>\n"
        f"• Команда <code>/mediastaff</code> — состав медиа{manage_hint}\n\n"
        f"<b>Все ранги медиа (1–8):</b>\n{render_media_ranks_table()}",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


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
    lines = [f"📋 <b>Игроки</b> (всего: <code>{len(items)}</code>):\n"]
    for u in items[:40]:
        has_tb = float(u.get("tempban_until", 0.0) or 0.0) > time.time()
        ban_tag = " 🚫" if u.get("banned") else (" ⏳" if has_tb else "")
        age_str = f", {u['age']} л." if u.get("age") else ""
        lines.append(
            f"• <b><code>#{u['game_id']}</code></b> {esc(u['name'])}{age_str} — {u['lvl']} ур. | {u['money'] + u['bank']} ₽{ban_tag}"
        )
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


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
    ranks_list = "\n".join(f"• <code>{k}</code> — <b>{esc(v['title'])}</b> ({esc(v['perm_desc'])})" for k, v in ADMIN_RANKS.items())
    lines = ["🛡 <b>Иерархия администрации (1–8):</b>\n" + ranks_list + "\n\n📋 <b>Текущий состав:</b>"]
    if not staff:
        lines.append("Администраторов пока нет.")
    else:
        for idx, (al, cr, nm, gid) in enumerate(staff, start=1):
            tag = " 👑 Создатель" if cr else ""
            lines.append(f"{idx}. <b>{esc(nm)}</b> (<code>#{gid}</code>) — <b>{esc(get_admin_title(al))}</b>{tag}")
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


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
        ranks_preview = "\n".join(f"• <code>{k}</code> — {esc(v['title'])} (+{v['ans_bonus']} ₽ за ответ)" for k, v in HELPER_RANKS.items())
        await safe_answer(
            message,
            f"Формат: <code>/sethelper &lt;игровой_ID&gt; &lt;0..8&gt;</code>\n\n<b>Иерархия хелперов:</b>\n{ranks_preview}",
            parse_mode="HTML",
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
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    target["helper_lvl"] = lvl
    save_state()
    title_str = get_helper_title(lvl)
    await safe_answer(
        message,
        f"🛟 Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) установлен ранг хелпера: <b>{esc(title_str)}</b>.",
        parse_mode="HTML",
    )
    if lvl > 0:
        await safe_send(bot, int(target["tg_id"]), f"🛟 Вам назначен ранг хелпера: <b>{esc(title_str)}</b>!", parse_mode="HTML")


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
    lines = [f"🛟 <b>Состав хелперов</b> (<code>{len(staff_list)}</code> чел.):\n"]
    for idx, (hl, ans_cnt, name, gid) in enumerate(staff_list, start=1):
        lines.append(f"{idx}. <b>{esc(name)}</b> (<code>#{gid}</code>) — <b>{esc(get_helper_title(hl))}</b> | ответов: <code>{ans_cnt}</code>")
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


@dp.message(Command("setmedia"))
async def cmd_setmedia(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Выдавать и менять ранги медиа можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(
            message,
            f"Формат: <code>/setmedia &lt;игровой_ID&gt; &lt;0..8&gt;</code> (0 — снять статус медиа)\n\n<b>Ранги медиа:</b>\n{render_media_ranks_table()}",
            parse_mode="HTML",
        )
        return
    try:
        gid = int(parts[1].lstrip("#"))
        val = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень должны быть числами.")
        return
    if not (0 <= val <= MEDIA_MAX_RANK):
        await safe_answer(message, f"Ранг медиа должен быть от <code>0</code> до <code>{MEDIA_MAX_RANK}</code>.", parse_mode="HTML")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    target["media_lvl"] = val
    target["is_media"] = bool(val > 0)
    save_state()
    title_str = get_media_title(val)
    await safe_answer(
        message,
        f"🎬 Статус медиа для <b>{esc(target['name'])}</b> (<code>#{gid}</code>): <b>{esc(title_str)}</b>.",
        parse_mode="HTML",
    )
    if val > 0:
        await safe_send(bot, int(target["tg_id"]), f"🎬 Вам назначен статус медиа: <b>{esc(title_str)}</b>!", parse_mode="HTML")
    else:
        await safe_send(bot, int(target["tg_id"]), "🎬 Ваш статус медиа был снят администрацией.", parse_mode="HTML")


@dp.message(Command("setadmin"))
async def cmd_setadmin(message: Message, bot: Bot):
    uid = message.from_user.id
    actor_lvl = get_admin_lvl(uid)
    if not (is_creator(uid) or actor_lvl >= 5):
        await safe_answer(message, "⛔ Назначать администраторов можно с 5 ранга администратора или создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        ranks_preview = "\n".join(f"• <code>{k}</code> — <b>{esc(v['title'])}</b>" for k, v in ADMIN_RANKS.items())
        await safe_answer(
            message,
            f"Формат: <code>/setadmin &lt;игровой_ID&gt; &lt;0..8&gt;</code>\n\n<b>Ранги администрации:</b>\n{ranks_preview}",
            parse_mode="HTML",
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
        await safe_answer(message, f"⛔ Вы не можете выдать ранг администратора <code>&gt;= {actor_lvl}</code> (ваш ранг: <code>{actor_lvl}</code>).", parse_mode="HTML")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
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
        f"🛡 Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) установлен уровень администратора: <b>{esc(title_str)}</b>.",
        parse_mode="HTML",
    )
    if lvl > 0:
        await safe_send(bot, target_tg_id, f"🛡 Вам назначен уровень администратора: <b>{esc(title_str)}</b>!", parse_mode="HTML")


@dp.message(Command("ban"))
async def cmd_ban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Банить игроков можно со 2 ранга администратора.")
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await safe_answer(message, "Формат: <code>/ban &lt;игровой_ID&gt; [причина]</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    if is_creator(int(target["tg_id"])):
        await safe_answer(message, "Нельзя заблокировать создателя.")
        return
    target["banned"] = True
    target["ban_reason"] = parts[2].strip() if len(parts) == 3 else "Нарушение правил сервера"
    save_state()
    await safe_answer(message, f"🚫 Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) заблокирован.", parse_mode="HTML")


@dp.message(Command("unban"))
async def cmd_unban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Разбанивать игроков можно со 2 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/unban &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    target["banned"] = False
    target["ban_reason"] = ""
    target["tempban_until"] = 0.0
    target["tempban_reason"] = ""
    save_state()
    await safe_answer(message, f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) разблокирован (сняты постоянный и временный баны).", parse_mode="HTML")


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
            "Формат: <code>/tempban &lt;игровой_ID&gt; &lt;срок&gt; [причина]</code>\n"
            "Примеры срока: <code>30m</code>, <code>2h</code>, <code>1d</code>, <code>1d12h</code>, <code>45</code> (минуты)",
            parse_mode="HTML",
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
            "Некорректный срок. Используйте формат вроде <code>15m</code>, <code>3h</code>, <code>2d</code> (до 365 дней).",
            parse_mode="HTML",
        )
        return

    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
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
        f"⏳ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) временно заблокирован на <b>{esc(dur_txt)}</b>.\n"
        f"Причина: <i>{esc(reason)}</i>",
        parse_mode="HTML",
    )
    await safe_send(
        bot,
        target_tg_id,
        f"⏳ Вы получили временный бан на <b>{esc(dur_txt)}</b>.\nПричина: {esc(reason)}",
        parse_mode="HTML",
    )


@dp.message(Command("untempban"))
async def cmd_untempban(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 2):
        await safe_answer(message, "⛔ Снимать временные баны можно со 2 ранга администратора.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/untempban &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return

    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return

    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return

    target["tempban_until"] = 0.0
    target["tempban_reason"] = ""
    save_state()
    await safe_answer(message, f"✅ Временный бан с игрока <b>{esc(target['name'])}</b> (<code>#{gid}</code>) снят.", parse_mode="HTML")


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
    lines = ["🏠 <b>Недвижимость Criminal Russia:</b>\n"]
    rows: list[list[InlineKeyboardButton]] = []
    for hid, h in SHOP_HOUSES.items():
        has_it = hid in owned
        status = "<i>(В собственности)</i>" if has_it else f"цена <b>{h['price']} ₽</b>"
        lines.append(f"• <b>{esc(h['name'])}</b> — {status}, бонус банка: <code>+{h['bonus_bank']} ₽/смена</code>")
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
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="HTML")


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
    lines = ["🚗 <b>Автосалон Criminal Russia:</b>\n"]
    rows: list[list[InlineKeyboardButton]] = []
    for cid, c in SHOP_CARS.items():
        has_it = cid in owned
        status = "<i>(В гараже)</i>" if has_it else f"цена <b>{c['price']} ₽</b>"
        lines.append(f"• <b>{esc(c['name'])}</b> — {status}, бонус смены: <code>+{c['bonus_work']} ₽</code>")
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
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="HTML")


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
            "👨‍👩‍👧‍👦 <b>Семьи</b>\n"
            "Вы пока не состоите в семье.\n"
            "Создать семью (стоимость <code>50 000 ₽</code>): <code>/createfam &lt;Название&gt;</code>",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
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
        f"👨‍👩‍👧‍👦 <b>Семья «{esc(fdata.get('name', fid))}»</b> (<code>#{esc(fid)}</code>)\n"
        f"👑 Глава: <b>{esc(owner_name)}</b> | Участников: <b><code>{len(members)}</code></b>\n"
        f"🏦 Общак семьи: <b>{balance} ₽</b>",
        reply_markup=kb,
        parse_mode="HTML",
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
        await safe_answer(message, "Формат: <code>/createfam &lt;Название семьи&gt;</code>", parse_mode="HTML")
        return
    fam_name = parts[1].strip()[:32]
    cost = 50000
    if p["money"] < cost:
        await safe_answer(message, f"Для создания семьи нужно <b>{cost} ₽</b> наличными.", parse_mode="HTML")
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
    await safe_answer(message, f"🎉 Семья <b>«{esc(fam_name)}»</b> (<code>#{esc(new_id)}</code>) создана!", reply_markup=main_kb(uid), parse_mode="HTML")


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
        if rk >= 10 or p.get("leader_of") == cur_fac or is_admin(uid, 3):
            rows.append([
                InlineKeyboardButton(text=f"📋 Заявки ({pending_apps})", callback_data=f"fac_apps:{cur_fac}"),
                InlineKeyboardButton(text="💸 Премия составу (10 000 ₽)", callback_data=f"fac_bonus:{cur_fac}"),
            ])
        rows.append([
            InlineKeyboardButton(text="🚪 Уволиться ПСЖ", callback_data="fac_leave_self"),
        ])
        text = (
            f"🏛 <b>Фракция: {esc(fdata['name'])}</b>\n"
            f"🎖 Ваша должность: <b>{esc(rk_title)}</b> (<code>{rk}/13</code> ранг) | Выговоров: <code>{p.get('f_warns', 0)}/3</code>\n"
            f"⭐ Очки службы: <b><code>{p['faction_points']}</code></b> | Базовый оклад: <code>{fdata['salary']} ₽</code>\n"
            f"🏦 Казна фракции: <b>{fs['treasury']} ₽</b> | 📦 Склад материалов: <b><code>{fs['materials']}</code> ед.</b>\n"
            f"🔥 Рейтинг влияния: <b><code>{fs['rating']}</code></b>\n\n"
            f"Команды: <code>/r &lt;текст&gt;</code>, <code>/d &lt;текст&gt;</code>, <code>/fdeposit &lt;сумма&gt;</code>, <code>/members</code>, <code>/fapps</code>, <code>/fwarn &lt;ID&gt; [причина]</code>"
        )
        await safe_answer(message, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
        return

    lines = [
        "🏛 <b>Фракции Criminal Russia RP</b> (вы сейчас <b>Гражданский</b>)\n"
        "Выберите организацию для подачи заявки или подработки у NPC:\n"
    ]
    rows = []
    for fid, fdata in FACTIONS.items():
        fs = get_fstate(fid)
        lines.append(
            f"• <b>{esc(fdata['name'])}</b> (<code>{esc(fid)}</code>) — от <code>{fdata['min_lvl']}</code> ур., оклад <code>{fdata['salary']} ₽</code>, "
            f"рейтинг <code>{fs['rating']}</code>, NPC: <i>{esc(fdata['npc'])}</i>"
        )
        rows.append([
            InlineKeyboardButton(text=f"📝 Вступить в {fdata['name']}", callback_data=f"fac_apply:{fid}"),
            InlineKeyboardButton(text=f"🤖 Задание ({fid})", callback_data=f"fac_npc:{fid}"),
        ])
    rows.append([InlineKeyboardButton(text="🏆 Рейтинг всех фракций", callback_data="fac_top")])
    await safe_answer(message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")


@dp.callback_query(F.data == "fac_top")
async def cb_fac_top(callback: CallbackQuery):
    ranking = []
    for fid, fdata in FACTIONS.items():
        fs = get_fstate(fid)
        cnt = sum(1 for u in users.values() if isinstance(u, dict) and u.get("faction") == fid)
        ranking.append((int(fs.get("rating", 0)), int(fs.get("treasury", 0)), cnt, fdata["name"]))
    ranking.sort(key=lambda x: (-x[0], -x[1]))
    lines = ["🏆 <b>Рейтинг влияния фракций:</b>\n"]
    for i, (rt, tr, cnt, fname) in enumerate(ranking, start=1):
        lines.append(f"{i}. <b>{esc(fname)}</b> — 🔥 <code>{rt}</code> очков | 🏦 <code>{tr} ₽</code> | 👥 <code>{cnt}</code> чел.")
    if callback.message:
        await safe_answer(callback.message, "\n".join(lines), parse_mode="HTML")
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
            r_val = 13 if u.get("leader_of") == fid else int(u.get("rank", 1))
            roster.append((r_val, str(u.get("name", "Игрок")), int(u.get("game_id", 0))))
    roster.sort(key=lambda x: (-x[0], x[1].lower()))
    lines = [f"👥 <b>Состав «{esc(FACTIONS[fid]['name'])}»</b> (<code>{len(roster)}</code>):\n"]
    for idx, (rv, nm, gid) in enumerate(roster[:25], start=1):
        lines.append(f"{idx}. <b>{esc(nm)}</b> (<code>#{gid}</code>) — {esc(get_faction_rank_title(fid, rv))} (<code>{rv}/13</code>)")
    if callback.message:
        await safe_answer(callback.message, "\n".join(lines), parse_mode="HTML")
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
            if u.get("leader_of") == fid or int(u.get("rank", 1)) >= 10:
                await safe_send(
                    bot,
                    int(k),
                    f"📩 Новая заявка в <b>{esc(fdata['name'])}</b> от <b>{esc(p['name'])}</b> (<code>#{p['game_id']}</code>, {p['lvl']} ур.)!\n"
                    f"Принять: <code>/faccept {p['game_id']}</code> | Отклонить: <code>/fdecline {p['game_id']}</code>",
                    parse_mode="HTML",
                )

    await callback.answer(f"Заявка в «{fdata['name']}» отправлена старшему составу!", show_alert=True)


@dp.callback_query(F.data.startswith("fac_apps:"))
async def cb_fac_apps(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if not (p.get("faction") == fid and (p.get("leader_of") == fid or int(p.get("rank", 1)) >= 10) or is_admin(uid, 3)):
        await callback.answer("Недостаточно прав для просмотра заявок", show_alert=True)
        return
    pending = [a for a in faction_apps.values() if isinstance(a, dict) and a.get("faction") == fid and a.get("status") == "pending"]
    if not pending:
        await callback.answer("Активных заявок нет", show_alert=True)
        return
    lines = [f"📋 <b>Заявки в «{esc(FACTIONS[fid]['name'])}»</b> (<code>{len(pending)}</code>):\n"]
    rows = []
    for a in pending[:10]:
        gid = a["game_id"]
        lines.append(f"• <b>{esc(a['name'])}</b> (<code>#{gid}</code>)")
        rows.append([
            InlineKeyboardButton(text=f"✅ Принять #{gid}", callback_data=f"fapp_ok:{fid}:{gid}"),
            InlineKeyboardButton(text=f"❌ Отклонить #{gid}", callback_data=f"fapp_no:{fid}:{gid}"),
        ])
    if callback.message:
        await safe_answer(callback.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("fapp_ok:"))
async def cb_fapp_ok(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    actor = get_player(uid, callback.from_user.full_name)
    _, fid, gid_s = callback.data.split(":", 2)
    gid = int(gid_s)
    if not (actor.get("faction") == fid and (actor.get("leader_of") == fid or int(actor.get("rank", 1)) >= 10) or is_admin(uid, 3)):
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
    await safe_send(bot, int(target["tg_id"]), f"🎉 Ваша заявка одобрена! Вы приняты в <b>{esc(FACTIONS[fid]['name'])}</b> на 1 ранг.", parse_mode="HTML")


@dp.callback_query(F.data.startswith("fapp_no:"))
async def cb_fapp_no(callback: CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    actor = get_player(uid, callback.from_user.full_name)
    _, fid, gid_s = callback.data.split(":", 2)
    gid = int(gid_s)
    if not (actor.get("faction") == fid and (actor.get("leader_of") == fid or int(actor.get("rank", 1)) >= 10) or is_admin(uid, 3)):
        await callback.answer("Нет прав", show_alert=True)
        return
    target = find_player_by_game_id(gid)
    if target:
        app_id = f"{target['tg_id']}_{fid}"
        if app_id in faction_apps:
            faction_apps[app_id]["status"] = "declined"
        save_state()
        await safe_send(bot, int(target["tg_id"]), f"❌ Ваша заявка в <b>{esc(FACTIONS[fid]['name'])}</b> отклонена.", parse_mode="HTML")
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
    pay = int(fdata["salary"] * (1 + rk * 0.12)) + random.randint(400, 1100)
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
    if rk < 9 and p["faction_points"] >= rk * 100:
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
    sal = int(FACTIONS[fid]["salary"] * (1 + (int(p["rank"]) - 1) * 0.1))
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
    if not (actor.get("faction") == fid and (actor.get("leader_of") == fid or int(actor.get("rank", 1)) >= 11) or is_admin(uid, 4)):
        await callback.answer("Выдавать премии из казны могут 11–13 ранги фракции", show_alert=True)
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
        await safe_send(bot, int(m["tg_id"]), f"💸 Руководство <b>{esc(FACTIONS[fid]['name'])}</b> выдало вам премию <b>+{share} ₽</b>!", parse_mode="HTML")
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
    while p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()
    await callback.answer(f"{fdata['npc']}: +{reward} ₽ и +30 XP!", show_alert=True)


@dp.message(Command("fwarn"))
async def cmd_fwarn(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 11 and actor.get("faction") in FACTIONS else None)
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Выдавать выговоры могут 11–13 ранги фракции или админы 3+ ранга.")
        return

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/fwarn &lt;игровой_ID&gt; [причина]</code>", parse_mode="HTML")
        return

    gid = int(parts[1])
    reason = parts[2].strip() if len(parts) == 3 and parts[2].strip() else "Нарушение устава"
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
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
        await safe_answer(message, f"❌ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) получил <b>3/3</b> выговора и уволен из фракции! Причина: <i>{esc(reason)}</i>", parse_mode="HTML")
        await safe_send(bot, int(target["tg_id"]), f"❌ Вы уволены из фракции за <b>3/3 выговоров</b>. Причина: {esc(reason)}", parse_mode="HTML")
        return

    target["f_warns"] = warns
    save_state()
    f_label = FACTIONS[t_fid]["name"] if t_fid in FACTIONS else "фракции"
    await safe_answer(message, f"⚠️ Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) выдан выговор <b><code>{warns}/3</code></b> в <b>{esc(f_label)}</b>. Причина: <i>{esc(reason)}</i>", parse_mode="HTML")
    await safe_send(bot, int(target["tg_id"]), f"⚠️ Вам выдан выговор <b><code>{warns}/3</code></b> в <b>{esc(f_label)}</b>. Причина: {esc(reason)}", parse_mode="HTML")


@dp.message(Command("fapps"))
async def cmd_fapps(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    if fid not in FACTIONS or (p.get("leader_of") != fid and int(p.get("rank", 1)) < 10 and not is_admin(uid, 3)):
        await safe_answer(message, "⛔ Просматривать заявки может старший состав фракции (10+ ранг).")
        return
    pending = [a for a in faction_apps.values() if isinstance(a, dict) and a.get("faction") == fid and a.get("status") == "pending"]
    if not pending:
        await safe_answer(message, "📋 Новых заявок во фракцию нет.")
        return
    lines = [f"📋 <b>Заявки в «{esc(FACTIONS[fid]['name'])}»</b> (<code>{len(pending)}</code>):\n"]
    for a in pending:
        lines.append(f"• <b>{esc(a['name'])}</b> (<code>#{a['game_id']}</code>) — <code>/faccept {a['game_id']}</code> или <code>/fdecline {a['game_id']}</code>")
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


@dp.message(Command("faccept"))
async def cmd_faccept(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("faction", "none")
    if fid not in FACTIONS or (actor.get("leader_of") != fid and int(actor.get("rank", 1)) < 10 and not is_admin(uid, 3)):
        await safe_answer(message, "⛔ Принимать заявки могут 10+ ранги фракции.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/faccept &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    target["faction"] = fid
    target["rank"] = 1
    target["f_warns"] = 0
    target["faction_points"] = 0
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "accepted"
    save_state()
    await safe_answer(message, f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) принят в <b>{esc(FACTIONS[fid]['name'])}</b>.", parse_mode="HTML")
    await safe_send(bot, int(target["tg_id"]), f"🎉 Ваша заявка одобрена! Вы приняты в <b>{esc(FACTIONS[fid]['name'])}</b>.", parse_mode="HTML")


@dp.message(Command("fdecline"))
async def cmd_fdecline(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("faction", "none")
    if fid not in FACTIONS or (actor.get("leader_of") != fid and int(actor.get("rank", 1)) < 10 and not is_admin(uid, 3)):
        await safe_answer(message, "⛔ Отклонять заявки могут 10+ ранги фракции.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/fdecline &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "declined"
    save_state()
    await safe_answer(message, f"❌ Заявка игрока <b>{esc(target['name'])}</b> (<code>#{gid}</code>) отклонена.", parse_mode="HTML")
    await safe_send(bot, int(target["tg_id"]), f"❌ Ваша заявка в <b>{esc(FACTIONS[fid]['name'])}</b> отклонена.", parse_mode="HTML")


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
        await safe_answer(message, "Формат: <code>/fdeposit &lt;сумма&gt;</code>", parse_mode="HTML")
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
        f"🏦 Вы пополнили казну <b>{esc(FACTIONS[fid]['name'])}</b> на <b>+{amt} ₽</b> (казна: <b>{fs['treasury']} ₽</b>).",
        parse_mode="HTML",
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
        await safe_answer(message, "Формат: <code>/r &lt;сообщение&gt;</code>", parse_mode="HTML")
        return
    rk_title = get_faction_rank_title(fid, int(p.get("rank", 1)))
    msg_txt = f"📡 <b>[{esc(FACTIONS[fid]['name'])}] {esc(rk_title)} {esc(p['name'])} (<code>#{p['game_id']}</code>):</b> {esc(parts[1].strip())}"
    sent = 0
    for k, u in users.items():
        if isinstance(u, dict) and u.get("faction") == fid:
            try:
                await safe_send(bot, int(k), msg_txt, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
    await safe_answer(message, f"✅ Отправлено в рацию (<code>{sent}</code> чел.).", parse_mode="HTML")


@dp.message(Command("invite"))
async def cmd_invite(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 10 and actor.get("faction") in FACTIONS else None)
    if not fid:
        await safe_answer(message, "⛔ Принимать во фракцию могут только лидеры или старший состав (10+ ранг).")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/invite &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    target["faction"] = fid
    target["rank"] = 1
    target["f_warns"] = 0
    target["faction_points"] = 0
    save_state()
    await safe_answer(message, f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) принят в <b>{esc(FACTIONS[fid]['name'])}</b>.", parse_mode="HTML")
    try:
        await safe_send(bot, int(target["tg_id"]), f"🏛 Вы приняты во фракцию <b>«{esc(FACTIONS[fid]['name'])}»</b>!", parse_mode="HTML")
    except Exception:
        pass


@dp.message(Command("uninvite"))
async def cmd_uninvite(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 11 and actor.get("faction") in FACTIONS else None)
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Увольнять из фракции могут 11–13 ранги или админы 3+ ранга.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/uninvite &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
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
    await safe_answer(message, f"🗑 Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) уволен из фракции.", parse_mode="HTML")


@dp.message(Command("setrank"))
async def cmd_setrank(message: Message):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 11 and actor.get("faction") in FACTIONS else None)
    if not fid and not is_admin(uid, 3):
        await safe_answer(message, "⛔ Менять ранги могут 11–13 ранги фракции или админы 3+ ранга.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: <code>/setrank &lt;игровой_ID&gt; &lt;1..13&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
        rk = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и ранг должны быть числами.")
        return
    if not (1 <= rk <= 13):
        await safe_answer(message, "Ранг должен быть от 1 до 13.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    if fid and target.get("faction") != fid:
        await safe_answer(message, "Игрок не состоит в вашей фракции.")
        return
    target_fid = target.get("faction", fid or "mvd")
    target["rank"] = rk
    save_state()
    rk_name = get_faction_rank_title(target_fid, rk)
    await safe_answer(
        message,
        f"⭐ Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) назначена должность: <b>{esc(rk_name)}</b> (<code>{rk}/13</code>).",
        parse_mode="HTML",
    )


@dp.message(Command("setleader"))
async def cmd_setleader(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Назначать лидеров можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: <code>/setleader &lt;игровой_ID&gt; &lt;фракция|none&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return
    fid = parts[2].strip().lower()
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    if fid == "none":
        target["leader_of"] = None
        save_state()
        await safe_answer(message, f"✅ Лидерство у <b>{esc(target['name'])}</b> (<code>#{gid}</code>) снято.", parse_mode="HTML")
        return
    if fid not in FACTIONS:
        await safe_answer(message, f"Неизвестная фракция. Доступно: {', '.join(FACTIONS.keys())}")
        return
    target["faction"] = fid
    target["rank"] = 13
    target["leader_of"] = fid
    save_state()
    await safe_answer(message, f"👑 <b>{esc(target['name'])}</b> (<code>#{gid}</code>) назначен лидером <b>«{esc(FACTIONS[fid]['name'])}»</b>!", parse_mode="HTML")


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
    lines = ["🏆 <b>Топ-10 богатейших игроков:</b>\n"]
    for idx, (cap, lvl, name, gid) in enumerate(items[:10], start=1):
        lines.append(f"{idx}. <b>{esc(name)}</b> (<code>#{gid}</code>) — <b>{cap} ₽</b> ({lvl} ур.)")
    await safe_answer(message, "\n".join(lines), reply_markup=main_kb(uid), parse_mode="HTML")


@dp.message(Command("givemoney"))
async def cmd_givemoney(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Выдавать валюту можно с 4 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await safe_answer(message, "Формат: <code>/givemoney &lt;игровой_ID&gt; &lt;сумма&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
        amt = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и сумма должны быть числами.")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    target["money"] += amt
    save_state()
    await safe_answer(message, f"💵 Выдано <b>{amt} ₽</b> игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>).", parse_mode="HTML")
    try:
        await safe_send(bot, int(target["tg_id"]), f"💵 Администрация начислила вам <b>{amt} ₽</b>!", parse_mode="HTML")
    except Exception:
        pass


@dp.message(Command("bank"))
async def cmd_bank(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) < 3 or parts[1].lower() not in {"dep", "deposit", "put", "take", "withdraw", "get"}:
        await safe_answer(
            message,
            f"🏦 <b>Банковский счёт</b>\n"
            f"Наличные: <b>{p['money']} ₽</b> | В банке: <b>{p['bank']} ₽</b>\n"
            "Положить: <code>/bank put &lt;сумма&gt;</code>\n"
            "Снять: <code>/bank take &lt;сумма&gt;</code>",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
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
        await safe_answer(message, f"🏦 Положено в банк <b>+{amt} ₽</b>. Баланс банка: <b>{p['bank']} ₽</b>.", reply_markup=main_kb(uid), parse_mode="HTML")
    else:
        if p["bank"] < amt:
            await safe_answer(message, "Недостаточно средств на банковском счёте.")
            return
        p["bank"] -= amt
        p["money"] += amt
        save_state()
        await safe_answer(message, f"💵 Снято с банка <b>+{amt} ₽</b>. Наличные: <b>{p['money']} ₽</b>.", reply_markup=main_kb(uid), parse_mode="HTML")


@dp.message(Command("resetplayer"))
async def cmd_resetplayer(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 5):
        await safe_answer(message, "⛔ Обнулять аккаунты игроков можно с 5 ранга администратора или создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await safe_answer(message, "Формат: <code>/resetplayer &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    try:
        gid = int(parts[1])
    except ValueError:
        await safe_answer(message, "Игровой ID должен быть числом.")
        return

    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
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
        f"♻️ Прогресс игрока <b>{esc(old_name)}</b> (<code>#{gid}</code>) полностью обнулён (баланс <code>0 ₽</code>, 1 уровень, без имущества/фракции/семьи).",
        parse_mode="HTML",
    )
    await safe_send(
        bot,
        target_tg_id,
        "♻️ Ваш игровой прогресс был обнулён администрацией.",
        parse_mode="HTML",
    )


@dp.message(Command("wipeall"))
async def cmd_wipeall(message: Message):
    global next_ticket_id
    uid = message.from_user.id
    if not is_creator(uid):
        await safe_answer(message, "⛔ Полный вайп сервера доступен только создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or parts[1].strip().upper() != "CONFIRM":
        await safe_answer(
            message,
            "⚠️ <b>Внимание!</b> Это полностью очистит базу игроков, бизнесов, семей, промокодов и тикетов.\n"
            "Для подтверждения введите: <code>/wipeall CONFIRM</code>",
            parse_mode="HTML",
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
    faction_state.clear()
    next_ticket_id = 1
    for fid, fdef in DEFAULT_FACTION_STATE.items():
        faction_state[fid] = dict(fdef)
    for bid, bdef in DEFAULT_BUSINESSES.items():
        businesses[bid] = dict(bdef)

    if creator_backup:
        users[str(CREATOR_ID)] = normalize_player(creator_backup, CREATOR_ID)

    save_state()
    await safe_answer(
        message,
        "🧹 <b>Полный вайп выполнен!</b> База сервера сброшена к чистому состоянию.",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
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
            f"🛠 <b>Режим технических работ:</b> <b>{status_txt}</b>\n"
            f"Причина: <i>{esc(maintenance_reason)}</i>\n\n"
            "Включить: <code>/tech on [причина]</code>\n"
            "Выключить: <code>/tech off</code>",
            parse_mode="HTML",
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
            f"🛠 <b>Технические работы ВКЛЮЧЕНЫ.</b>\n"
            f"Причина: <i>{esc(maintenance_reason)}</i>\n"
            "Игрокам бот будет отвечать уведомлением о техработах, админы 1+ ранга и создатель продолжают работу.",
            parse_mode="HTML",
        )
    elif mode_arg in {"off", "0", "false", "нет"}:
        maintenance_mode = False
        save_state()
        await safe_answer(
            message,
            "✅ <b>Технические работы ВЫКЛЮЧЕНЫ.</b> Бот снова доступен всем игрокам.",
            parse_mode="HTML",
        )
    else:
        await safe_answer(
            message,
            "Формат: <code>/tech on [причина]</code> или <code>/tech off</code>",
            parse_mode="HTML",
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
