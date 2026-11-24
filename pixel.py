import asyncio
import html
import io
import json
import os
import random
import re
import time
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except Exception:
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]
    PIL_AVAILABLE = False


BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE")
DATA_FILE = os.getenv("DATA_FILE", "crmp_russia_data.json")
PASSPORT_TEMPLATE_PATH = os.getenv("PASSPORT_TEMPLATE_PATH", "passport_template.png")
FONT_PATH = os.getenv("FONT_PATH", "")
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

FAMILY_CREATE_COST = 50000
FAMILY_UPGRADE_BASE_COST = 900000
FAMILY_DAILY_CONTRACTS_LIMIT = 2

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
    "💨 Вейп",
}

ADMIN_RANKS: dict[int, dict[str, Any]] = {
    1: {"title": "Младший стажёр-администратор", "perm_desc": "Базовый надзор и просмотр игроков"},
    2: {"title": "Стажёр администрации", "perm_desc": "Просмотр карточек игроков и тикетов"},
    3: {"title": "Младший модератор", "perm_desc": "Мут рации департамента и базовый контроль"},
    4: {"title": "Модератор", "perm_desc": "Временные баны и проверка нарушений"},
    5: {"title": "Старший модератор", "perm_desc": "Постоянные баны и разбаны"},
    6: {"title": "Младший администратор", "perm_desc": "Надзор за составами фракций и событиями"},
    7: {"title": "Администратор", "perm_desc": "Промокоды, смена ников и выговоры фракций"},
    8: {"title": "Старший администратор", "perm_desc": "Управление составами, промокодами и наказаниями"},
    9: {"title": "Ведущий администратор", "perm_desc": "Контроль мероприятий, фракций и экономики"},
    10: {"title": "Следящий за фракциями", "perm_desc": "Надзор за лидерами, казной и фракциями"},
    11: {"title": "Куратор состава", "perm_desc": "Выдача валюты, хелперы, медиа, лидерки и техработы"},
    12: {"title": "Главный куратор проекта", "perm_desc": "Координация кураторов, медиа и фракций"},
    13: {"title": "Заместитель ГА", "perm_desc": "Назначение админов (до 13 ур.) и контроль персонала"},
    14: {"title": "Главный администратор (ГА)", "perm_desc": "Назначение админов (до 14 ур.) и обнуление аккаунтов"},
    15: {"title": "Руководитель проекта", "perm_desc": "Назначение админов (до 15 ур.) и глобальные настройки"},
    16: {"title": "Специальный администратор", "perm_desc": "Высший административный уровень перед создателем"},
}

ADMIN_MAX_RANK = max(ADMIN_RANKS.keys())

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

# --- РАСШИРЕННЫЕ RP-ЗАДАНИЯ И СЦЕНАРИИ ПО ФРАКЦИЯМ ---
FACTION_TASKS: dict[str, list[dict[str, Any]]] = {
    "court": [
        {
            "id": "court_case_review",
            "title": "Изучить материалы дела и доказательства",
            "rp_prompt": "Вы открыли том дела №408. В протоколе обнаружено расхождение во времени допроса и показаниях свидетеля.",
            "duration_sec": 180,
            "reward_money": 2600,
            "reward_xp": 45,
            "points": 18,
            "treasury_cut": 700,
            "stamina": 12,
            "hunger": 8,
        },
        {
            "id": "court_protocols",
            "title": "Проверить протоколы задержаний и ордера",
            "rp_prompt": "Оперативники принесли запрос на обыск по громкому делу. Нужно сверить основания и подписи прокурора.",
            "duration_sec": 300,
            "reward_money": 4400,
            "reward_xp": 70,
            "points": 28,
            "treasury_cut": 1100,
            "stamina": 18,
            "hunger": 12,
        },
        {
            "id": "court_summons",
            "title": "Оформить повестки и судебные запросы",
            "rp_prompt": "Назначено заседание по экономическому спору. Требуется разослать повестки сторонам и запросить выписки из реестра.",
            "duration_sec": 420,
            "reward_money": 6200,
            "reward_xp": 95,
            "points": 38,
            "treasury_cut": 1500,
            "stamina": 22,
            "hunger": 15,
        },
        {
            "id": "court_hearing",
            "title": "Провести открытое судебное слушание",
            "rp_prompt": "В зале заседаний пресса и стороны процесса. Адвокат заявляет ходатайство об отводе свидетеля.",
            "duration_sec": 600,
            "reward_money": 9200,
            "reward_xp": 135,
            "points": 55,
            "treasury_cut": 2300,
            "stamina": 28,
            "hunger": 20,
        },
    ],
    "mvd": [
        {
            "id": "mvd_patrol",
            "title": "Патрулирование улиц и дворов",
            "rp_prompt": "Экипаж заступил на маршрут. Во дворе замечена подозрительная компания у припаркованного авто без номеров.",
            "duration_sec": 240,
            "reward_money": 3400,
            "reward_xp": 55,
            "points": 22,
            "treasury_cut": 850,
            "stamina": 18,
            "hunger": 12,
        },
        {
            "id": "mvd_statements",
            "title": "Приём и регистрация заявлений граждан",
            "rp_prompt": "В дежурную часть обратился гражданин с заявлением о пропаже документов и подозрительном переводе.",
            "duration_sec": 180,
            "reward_money": 2500,
            "reward_xp": 40,
            "points": 16,
            "treasury_cut": 600,
            "stamina": 10,
            "hunger": 8,
        },
        {
            "id": "mvd_wanted_check",
            "title": "Отработка ориентировок по розыску",
            "rp_prompt": "По ориентировке проходит подозреваемый, замеченный у вокзала. Необходимо проверить камеры и перекрыть выходы.",
            "duration_sec": 480,
            "reward_money": 6800,
            "reward_xp": 100,
            "points": 42,
            "treasury_cut": 1700,
            "stamina": 25,
            "hunger": 16,
        },
        {
            "id": "mvd_raid_check",
            "title": "Рейд по точкам сбыта и документам",
            "rp_prompt": "Совместная проверка торговых точек и документов посетителей на предмет нахождения в розыске.",
            "duration_sec": 540,
            "reward_money": 7900,
            "reward_xp": 115,
            "points": 48,
            "treasury_cut": 1950,
            "stamina": 26,
            "hunger": 18,
        },
    ],
    "dps": [
        {
            "id": "dps_post",
            "title": "Дежурство на контрольном посту",
            "rp_prompt": "На посту ДПС останавливается тонированный седан. Водитель нервничает и не сразу передаёт документы.",
            "duration_sec": 240,
            "reward_money": 3200,
            "reward_xp": 50,
            "points": 20,
            "treasury_cut": 800,
            "stamina": 15,
            "hunger": 10,
        },
        {
            "id": "dps_speed",
            "title": "Контроль скоростного режима на трассе",
            "rp_prompt": "Радар зафиксировал превышение скорости на 75 км/ч на загородном участке.",
            "duration_sec": 360,
            "reward_money": 4900,
            "reward_xp": 75,
            "points": 30,
            "treasury_cut": 1200,
            "stamina": 20,
            "hunger": 14,
        },
        {
            "id": "dps_escort",
            "title": "Сопровождение колонны и разбор ДТП",
            "rp_prompt": "На перекрёстке произошло столкновение двух машин с перекрытием полосы, следом идёт колонна.",
            "duration_sec": 540,
            "reward_money": 7600,
            "reward_xp": 115,
            "points": 48,
            "treasury_cut": 1900,
            "stamina": 26,
            "hunger": 18,
        },
    ],
    "pps": [
        {
            "id": "pps_square",
            "title": "Патрулирование вокзалов и площадей",
            "rp_prompt": "На центральной площади скопление людей и поступила жалоба на уличного дебошира.",
            "duration_sec": 210,
            "reward_money": 2900,
            "reward_xp": 45,
            "points": 18,
            "treasury_cut": 700,
            "stamina": 16,
            "hunger": 10,
        },
        {
            "id": "pps_night",
            "title": "Ночной обход спального района",
            "rp_prompt": "Поздний обход дворов. В тёмном переулке сработала сигнализация на складе.",
            "duration_sec": 420,
            "reward_money": 5700,
            "reward_xp": 85,
            "points": 36,
            "treasury_cut": 1400,
            "stamina": 22,
            "hunger": 15,
        },
    ],
    "fsb": [
        {
            "id": "fsb_surv",
            "title": "Скрытое наблюдение за объектом",
            "rp_prompt": "Фигурант оперативной разработки вышел на встречу у заброшенного ангара.",
            "duration_sec": 360,
            "reward_money": 5400,
            "reward_xp": 85,
            "points": 34,
            "treasury_cut": 1350,
            "stamina": 20,
            "hunger": 12,
        },
        {
            "id": "fsb_dossiers",
            "title": "Проверка закрытых досье и архивов",
            "rp_prompt": "Поднят закрытый архив по коррупционной схеме в области. Сверяете проводки и связи.",
            "duration_sec": 480,
            "reward_money": 7200,
            "reward_xp": 110,
            "points": 45,
            "treasury_cut": 1800,
            "stamina": 18,
            "hunger": 14,
        },
        {
            "id": "fsb_intercept",
            "title": "Оперативный перехват и брифинг",
            "rp_prompt": "Получена информация о передаче крупной суммы криминальным структурам.",
            "duration_sec": 600,
            "reward_money": 9600,
            "reward_xp": 140,
            "points": 60,
            "treasury_cut": 2400,
            "stamina": 28,
            "hunger": 20,
        },
    ],
    "fsin": [
        {
            "id": "fsin_cells",
            "title": "Обход камер и проверка режима",
            "rp_prompt": "Плановый обход корпусов и проверка камер на предмет нарушений режима.",
            "duration_sec": 240,
            "reward_money": 3500,
            "reward_xp": 55,
            "points": 22,
            "treasury_cut": 850,
            "stamina": 16,
            "hunger": 10,
        },
        {
            "id": "fsin_convoy",
            "title": "Подготовка и сопровождение конвоя",
            "rp_prompt": "Формируется автозак для этапирования задержанного в суд. Проверяете связь и маршрут.",
            "duration_sec": 480,
            "reward_money": 6700,
            "reward_xp": 100,
            "points": 42,
            "treasury_cut": 1650,
            "stamina": 25,
            "hunger": 16,
        },
    ],
    "mchs": [
        {
            "id": "mchs_equip",
            "title": "Проверка пожарной техники и рукавов",
            "rp_prompt": "Перед заступлением на дежурство проверяете давление в насосах, аппараты и рукава.",
            "duration_sec": 210,
            "reward_money": 3100,
            "reward_xp": 50,
            "points": 20,
            "treasury_cut": 750,
            "stamina": 16,
            "hunger": 10,
        },
        {
            "id": "mchs_fire",
            "title": "Тушение условного возгорания на складе",
            "rp_prompt": "Поступил вызов о задымлении на промскладе. Внутри могут оставаться люди.",
            "duration_sec": 450,
            "reward_money": 6300,
            "reward_xp": 95,
            "points": 40,
            "treasury_cut": 1550,
            "stamina": 26,
            "hunger": 16,
        },
    ],
    "med": [
        {
            "id": "med_stock",
            "title": "Инвентаризация медикаментов и аптечек",
            "rp_prompt": "Проверяете остатки препаратов, сроки годности и укомплектованность сумок.",
            "duration_sec": 180,
            "reward_money": 2700,
            "reward_xp": 45,
            "points": 18,
            "treasury_cut": 650,
            "stamina": 12,
            "hunger": 8,
        },
        {
            "id": "med_shift",
            "title": "Дежурство в приёмном отделении",
            "rp_prompt": "В приёмный покой доставили пациента с резким скачком давления и болью в груди.",
            "duration_sec": 390,
            "reward_money": 5600,
            "reward_xp": 85,
            "points": 35,
            "treasury_cut": 1400,
            "stamina": 20,
            "hunger": 14,
        },
        {
            "id": "med_ambulance",
            "title": "Смена на выездной бригаде скорой",
            "rp_prompt": "Срочный вызов на трассу после аварии. Бригада выдвигается с сиреной.",
            "duration_sec": 540,
            "reward_money": 7900,
            "reward_xp": 120,
            "points": 50,
            "treasury_cut": 1950,
            "stamina": 25,
            "hunger": 18,
        },
    ],
    "smi": [
        {
            "id": "smi_news",
            "title": "Подготовка сводки новостей области",
            "rp_prompt": "Собираете главные события дня для вечернего выпуска: дороги, экономика и службы.",
            "duration_sec": 210,
            "reward_money": 3000,
            "reward_xp": 45,
            "points": 18,
            "treasury_cut": 750,
            "stamina": 12,
            "hunger": 10,
        },
        {
            "id": "smi_broadcast",
            "title": "Проведение прямого эфира и интервью",
            "rp_prompt": "Красный индикатор эфира включён. В студии гость, зрители присылают вопросы.",
            "duration_sec": 420,
            "reward_money": 5900,
            "reward_xp": 90,
            "points": 38,
            "treasury_cut": 1450,
            "stamina": 18,
            "hunger": 14,
        },
    ],
    "vo": [
        {
            "id": "vo_guard",
            "title": "Караул на КПП воинской части",
            "rp_prompt": "На КПП подъехал транспорт без пропуска. Проверяете документы и докладываете.",
            "duration_sec": 240,
            "reward_money": 3500,
            "reward_xp": 55,
            "points": 22,
            "treasury_cut": 850,
            "stamina": 18,
            "hunger": 12,
        },
        {
            "id": "vo_drill",
            "title": "Строевая и тактическая подготовка",
            "rp_prompt": "На плацу и полигоне проходит отработка нормативов и построения.",
            "duration_sec": 480,
            "reward_money": 6900,
            "reward_xp": 105,
            "points": 44,
            "treasury_cut": 1700,
            "stamina": 28,
            "hunger": 18,
        },
    ],
    "gov": [
        {
            "id": "gov_docs",
            "title": "Оформление указов и постановлений",
            "rp_prompt": "Готовите проект распоряжения администрации области и проверяете формулировку.",
            "duration_sec": 240,
            "reward_money": 3800,
            "reward_xp": 60,
            "points": 24,
            "treasury_cut": 950,
            "stamina": 12,
            "hunger": 10,
        },
        {
            "id": "gov_audit",
            "title": "Выездная проверка госучреждений",
            "rp_prompt": "Комиссия прибыла с проверкой расходования средств и соблюдения регламентов.",
            "duration_sec": 480,
            "reward_money": 7400,
            "reward_xp": 110,
            "points": 46,
            "treasury_cut": 1850,
            "stamina": 22,
            "hunger": 15,
        },
    ],
    "opg_sun": [
        {
            "id": "opg_sun_points",
            "title": "Обход подконтрольных точек",
            "rp_prompt": "Проверяете точки под крышей «Солнцевских» и собираете отчёт о ситуации на районе.",
            "duration_sec": 240,
            "reward_money": 3600,
            "reward_xp": 60,
            "points": 24,
            "treasury_cut": 900,
            "stamina": 18,
            "hunger": 12,
        },
        {
            "id": "opg_sun_meeting",
            "title": "Сходка и распределение долей",
            "rp_prompt": "На сходке обсуждаются новые территории и доля в общак. Нужен холодный расчёт.",
            "duration_sec": 480,
            "reward_money": 7100,
            "reward_xp": 105,
            "points": 44,
            "treasury_cut": 1750,
            "stamina": 24,
            "hunger": 16,
        },
    ],
    "opg_orekh": [
        {
            "id": "opg_orekh_scout",
            "title": "Разведка маршрутов перед делом",
            "rp_prompt": "Изучаете график движения, камеры и посты патрулей на намеченном участке.",
            "duration_sec": 270,
            "reward_money": 4000,
            "reward_xp": 65,
            "points": 26,
            "treasury_cut": 1000,
            "stamina": 20,
            "hunger": 12,
        },
        {
            "id": "opg_orekh_heist",
            "title": "Крупная акция и уход от погони",
            "rp_prompt": "Дело идёт по плану, но в районе замечены сирены. Нужно сработать чётко.",
            "duration_sec": 540,
            "reward_money": 8200,
            "reward_xp": 120,
            "points": 50,
            "treasury_cut": 2050,
            "stamina": 28,
            "hunger": 18,
        },
    ],
}

FACTION_RP_SCENARIOS: dict[str, list[dict[str, Any]]] = {
    "law": [
        {
            "id": "law_stop",
            "title": "Остановка подозрительного авто",
            "desc": "На трассе водитель проигнорировал требование об остановке и свернул на просёлок.",
            "opt_a": ("🚨 Блокировать выезд и досмотреть салон", 4200, 65, 22),
            "opt_b": ("📡 Вызвать подкрепление и вести наблюдение", 3500, 55, 26),
        },
        {
            "id": "law_alarm",
            "title": "Тревожный сигнал с объекта",
            "desc": "Сработала тревожная кнопка. Внутри здания возможен конфликт или вооружённый нарушитель.",
            "opt_a": ("🛡 Действовать жёстко и перекрыть периметр", 5200, 80, 28),
            "opt_b": ("🎙 Потребовать сдаться через громкоговоритель", 4400, 70, 30),
        },
    ],
    "gov": [
        {
            "id": "gov_crisis",
            "title": "Экстренное совещание по ситуации в городе",
            "desc": "Поступило обращение о сбое на объекте и нехватке ресурсов. Нужно принять решение.",
            "opt_a": ("📑 Выделить экстренный резерв и назначить контроль", 4500, 70, 24),
            "opt_b": ("🤝 Созвать профильные службы и согласовать план", 3800, 60, 28),
        },
        {
            "id": "gov_appeal",
            "title": "Спорная жалоба на приёме граждан",
            "desc": "Заявитель предъявляет документы о нарушении сроков рассмотрения дела.",
            "opt_a": ("⚖️ Вынести мотивированное решение на месте", 4100, 65, 22),
            "opt_b": ("📂 Запросить материалы и провести проверку", 3600, 55, 25),
        },
    ],
    "crime": [
        {
            "id": "crime_deal",
            "title": "Стрелка за спорную точку",
            "desc": "Конкуренты пытаются забрать выгодный район. На месте уже собрались бойцы.",
            "opt_a": ("🔥 Поставить жёсткий ультиматум и забрать долю", 5400, 85, 30),
            "opt_b": ("💼 Договориться о разделе влияния на выгодных условиях", 4300, 70, 25),
        },
        {
            "id": "crime_tail",
            "title": "Проверка на «хвост» после дела",
            "desc": "В зеркале заднего вида дважды мелькнула неприметная машина.",
            "opt_a": ("🚗 Сменить маршрут через промзону и оторваться", 4600, 75, 26),
            "opt_b": ("🕶 Уйти в тень, скинуть лишнее и переждать", 3900, 65, 28),
        },
    ],
}

RANK_UP_POINTS_PER_RANK = 60
FACTION_BONUS_COOLDOWN = 600

FACTIONS: dict[str, dict[str, Any]] = {
    "court": {
        "name": "Суд области",
        "type": "gov",
        "salary": 2250,
        "npc": "Председатель суда Соловьёв",
        "min_lvl": 2,
        "mission_name": "Судебное производство",
        "ranks": {
            1: "Секретарь заседания",
            2: "Помощник судьи",
            3: "Судебный пристав",
            4: "Консультант суда",
            5: "Старший секретарь",
            6: "Советник юстиции",
            7: "Мировой судья",
            8: "Судья районного суда",
            9: "Судья областного суда",
            10: "Член президиума суда",
            11: "Заместитель председателя суда",
            12: "Первый заместитель председателя",
            13: "Председатель суда",
        },
    },
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

VAPE_DEVICES: dict[str, dict[str, Any]] = {
    "pod_mini": {"name": "Pod-система Mini", "price": 1800, "stamina_bonus": 6, "mood_xp": 8},
    "pod_pro": {"name": "Pod-система Air Pro", "price": 3800, "stamina_bonus": 10, "mood_xp": 14},
    "boxmod": {"name": "BoxMod 120W", "price": 7500, "stamina_bonus": 16, "mood_xp": 22},
}

VAPE_FLAVORS: list[str] = [
    "🍓 Клубничный лёд",
    "🍏 Зелёное яблоко",
    "🌿 Холодная мята",
    "🫐 Черничный микс",
    "🥭 Тропический манго",
    "☕️ Ванильный капучино",
]

VAPE_REFILL_COST = 450
VAPE_CHARGE_COST = 350
VAPE_PUFF_COOLDOWN = 20

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

FAMILY_WEAPONS: dict[str, dict[str, Any]] = {
    "makarov": {"name": "Пистолет Макарова", "price": 45000, "rep_bonus": 10},
    "ak74": {"name": "Автомат АК-74", "price": 135000, "rep_bonus": 25},
    "saiga": {"name": "Карабин Сайга-12", "price": 195000, "rep_bonus": 35},
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


class RegistrationStates(StatesGroup):
    waiting_nickname = State()


class SupportStates(StatesGroup):
    choosing_category = State()
    waiting_message = State()
    replying_ticket = State()


class FamilyStates(StatesGroup):
    inviting_member = State()
    renaming_family = State()
    depositing_treasury = State()


def esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""), quote=False)


def clamp_stat(val: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(val)))


def format_rub(amount: int) -> str:
    sign = "-" if amount < 0 else ""
    digits = f"{abs(int(amount)):,}".replace(",", ".")
    return f"{sign}{digits} руб."


def get_reputation_title(rep: int) -> str:
    if rep >= 500:
        return "Легенда области"
    if rep >= 200:
        return "Уважаемый житель"
    if rep >= 50:
        return "Авторитет"
    if rep >= 10:
        return "Свой человек"
    if rep >= 0:
        return "Новичок"
    return "Неблагонадёжный"


def get_world_time_and_weather() -> tuple[str, str]:
    now_dt = datetime.now()
    time_str = now_dt.strftime("%H:%M")
    hour = now_dt.hour
    if 5 <= hour < 11:
        weather = "СВЕЖО"
    elif 11 <= hour < 17:
        weather = "ЯСНО"
    elif 17 <= hour < 22:
        weather = "ПРОХЛАДНО"
    else:
        weather = "ТУМАННО"
    return time_str, weather


def validate_rp_nick(nick: str) -> tuple[bool, str]:
    clean = nick.strip()
    if len(clean) < 5 or len(clean) > 31:
        return False, "Ник должен быть в формате <code>Имя_Фамилия</code> (от 5 до 31 символа, без пробелов)."
    if not NICK_RE.match(clean):
        return False, "Неверный формат ника. Используйте <code>Имя_Фамилия</code> (например, <code>Никита_Шакуров</code> или <code>Ivan_Volkov</code>)."
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

    raw_name = str(u.get("name") or "").strip()
    if not raw_name:
        raw_name = f"Игрок_{tg_id}"
    u["name"] = raw_name
    u["registered"] = bool(u.get("registered", False)) or bool(NICK_RE.match(raw_name))
    u["reg_date"] = str(u.get("reg_date") or datetime.now().strftime("%d %B %Y г."))

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
    u["reputation"] = int(u.get("reputation", 25))
    u["money"] = int(u.get("money", 5000))
    u["bank"] = int(u.get("bank", 0))
    u["hp"] = clamp_stat(u.get("hp", 100))
    u["hunger"] = clamp_stat(u.get("hunger", 100))
    u["stamina"] = clamp_stat(u.get("stamina", 100))
    u["faction"] = str(u.get("faction") or "none")
    u["rank"] = max(1, min(13, int(u.get("rank", 1))))
    u["f_warns"] = max(0, min(3, int(u.get("f_warns", 0))))
    u["leader_of"] = u.get("leader_of") if u.get("leader_of") in FACTIONS else None
    u["admin_lvl"] = max(0, min(ADMIN_MAX_RANK, int(u.get("admin_lvl", 0))))
    u["helper_lvl"] = max(0, min(8, int(u.get("helper_lvl", 0))))
    u["helper_answers"] = max(0, int(u.get("helper_answers", 0)))
    u["faction_points"] = max(0, int(u.get("faction_points", 0)))
    u["last_fmission"] = float(u.get("last_fmission", 0.0))

    raw_task_id = u.get("active_ftask_id")
    u["active_ftask_id"] = str(raw_task_id) if raw_task_id else None
    u["active_ftask_ends_at"] = float(u.get("active_ftask_ends_at", 0.0) or 0.0)

    u["has_vape"] = bool(u.get("has_vape", False))
    u["vape_key"] = str(u.get("vape_key") or "")
    u["vape_name"] = str(u.get("vape_name") or "")
    u["vape_liquid"] = clamp_stat(u.get("vape_liquid", 0))
    u["vape_battery"] = clamp_stat(u.get("vape_battery", 0))
    u["vape_puffs"] = max(0, int(u.get("vape_puffs", 0)))
    u["last_vape_puff"] = float(u.get("last_vape_puff", 0.0) or 0.0)

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
    u["tempban_until"] = float(u.get("tempban_until", 0.0) or 0.0)
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


def normalize_family(fdata: dict[str, Any], fid: str) -> dict[str, Any]:
    today_str = datetime.now().strftime("%Y-%m-%d")
    fdata["id"] = str(fid)
    fdata["name"] = str(fdata.get("name") or f"Семья_{fid}")
    fdata["owner_uid"] = int(fdata.get("owner_uid", 0))
    fdata["owner_name"] = str(fdata.get("owner_name") or "Глава")
    members = [int(m) for m in (fdata.get("members") or []) if str(m).lstrip("-").isdigit()]
    if fdata["owner_uid"] and fdata["owner_uid"] not in members:
        members.insert(0, fdata["owner_uid"])
    fdata["members"] = members
    fdata["balance"] = max(0, int(fdata.get("balance", 0)))
    fdata["tokens"] = max(0, int(fdata.get("tokens", 0)))
    fdata["reputation"] = int(fdata.get("reputation", 0))
    fdata["level"] = max(1, int(fdata.get("level", 1)))
    fdata["max_members"] = max(len(members), int(fdata.get("max_members", 8)))
    fdata["max_cars"] = max(1, int(fdata.get("max_cars", 3)))
    fdata["has_mansion"] = bool(fdata.get("has_mansion", False))
    fdata["mansion_name"] = str(fdata.get("mansion_name") or "Рублёвский особняк")
    fdata["tanker_fuel"] = max(0, int(fdata.get("tanker_fuel", 0)))
    fdata["warehouse_items"] = max(0, int(fdata.get("warehouse_items", 0)))
    fdata["cars"] = [str(c) for c in (fdata.get("cars") or [])]
    fdata["weapons"] = [str(w) for w in (fdata.get("weapons") or [])]
    fdata["ranks"] = dict(fdata.get("ranks") or {})
    if fdata.get("contracts_date") != today_str:
        fdata["contracts_date"] = today_str
        fdata["contracts_done"] = 0
    else:
        fdata["contracts_done"] = max(0, int(fdata.get("contracts_done", 0)))
    return fdata


def get_player(tg_id: int, full_name: str = "") -> dict[str, Any]:
    key = str(tg_id)
    if key not in users or not isinstance(users[key], dict):
        users[key] = normalize_player(
            {
                "name": full_name or f"Игрок_{tg_id}",
                "registered": False,
                "reg_date": datetime.now().strftime("%d %B %Y г."),
            },
            tg_id,
        )
        save_state()
    else:
        normalize_player(users[key], tg_id)
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
        return ADMIN_MAX_RANK
    u = users.get(str(uid))
    if not isinstance(u, dict):
        return 0
    return max(0, min(ADMIN_MAX_RANK, int(u.get("admin_lvl", 0))))


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


def get_faction_tasks(fid: str) -> list[dict[str, Any]]:
    if fid in FACTION_TASKS:
        return FACTION_TASKS[fid]
    fdata = FACTIONS.get(fid, {})
    base_name = fdata.get("mission_name") or "Служба во фракции"
    return [
        {
            "id": f"{fid}_shift_short",
            "title": f"{base_name} (короткая смена)",
            "duration_sec": 240,
            "reward_money": 3200,
            "reward_xp": 50,
            "points": 20,
            "treasury_cut": 800,
            "stamina": 15,
            "hunger": 10,
        },
        {
            "id": f"{fid}_shift_long",
            "title": f"{base_name} (усиленная смена)",
            "duration_sec": 480,
            "reward_money": 6400,
            "reward_xp": 95,
            "points": 40,
            "treasury_cut": 1600,
            "stamina": 25,
            "hunger": 16,
        },
    ]


def find_faction_task(fid: str, task_id: str | None) -> dict[str, Any] | None:
    if not task_id:
        return None
    for t in get_faction_tasks(fid):
        if t.get("id") == task_id:
            return t
    return None


def get_fstate(fid: str) -> dict[str, Any]:
    if fid not in faction_state:
        faction_state[fid] = dict(
            DEFAULT_FACTION_STATE.get(
                fid,
                {
                    "treasury": 25000,
                    "materials": 500,
                    "rating": 0,
                    "last_raid": 0.0,
                    "last_bonus": 0.0,
                },
            )
        )
    return faction_state[fid]


def is_police_faction(u: dict[str, Any]) -> bool:
    return str(u.get("faction") or "") in {"mvd", "dps", "pps", "fsb", "fsin", "vo"} or is_admin(
        int(u.get("tg_id", 0)), 1
    )


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
    maintenance_reason = str(
        raw.get("maintenance_reason") or "Проводятся технические работы. Попробуйте позже."
    )

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
            base = dict(
                DEFAULT_BUSINESSES.get(
                    bid,
                    {
                        "name": str(bval.get("name") or bid),
                        "price": int(bval.get("price", 1000000)),
                        "income_per_hour": int(bval.get("income_per_hour", 5000)),
                        "owner_uid": None,
                        "owner_name": None,
                        "cash": 0,
                        "last_collect": 0.0,
                    },
                )
            )
            base.update(bval)
            businesses[str(bid)] = base

    raw_fams = raw.get("families") if isinstance(raw.get("families"), dict) else {}
    for fid, fval in raw_fams.items():
        if isinstance(fval, dict):
            families[str(fid)] = normalize_family(dict(fval), str(fid))

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


def _load_font(size: int, bold: bool = False):
    if not PIL_AVAILABLE or ImageFont is None:
        return None
    candidates: list[str] = []
    if FONT_PATH:
        candidates.append(FONT_PATH)
    if bold:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        )
    else:
        candidates.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ]
        )
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def _build_passport_card_bytes(p: dict[str, Any], avatar_bytes: bytes | None = None) -> bytes | None:
    if not PIL_AVAILABLE or Image is None or ImageDraw is None:
        return None

    width, height = 1000, 560
    if PASSPORT_TEMPLATE_PATH and os.path.exists(PASSPORT_TEMPLATE_PATH):
        try:
            canvas = Image.open(PASSPORT_TEMPLATE_PATH).convert("RGBA").resize((width, height))
        except Exception:
            canvas = Image.new("RGBA", (width, height), (242, 232, 227, 255))
    else:
        canvas = Image.new("RGBA", (width, height), (242, 232, 227, 255))
        draw_bg = ImageDraw.Draw(canvas)
        draw_bg.rounded_rectangle([18, 18, width - 18, height - 18], radius=28, fill=(246, 238, 234, 255), outline=(128, 96, 82, 255), width=4)
        title_font = _load_font(30, bold=True)
        draw_bg.text((width // 2, 46), "★  ПАСПОРТ ГРАЖДАНИНА  ★", fill=(104, 74, 62, 255), font=title_font, anchor="mm")

        labels_left = [
            (340, 125, "ФАМИЛИЯ"),
            (340, 215, "ИМЯ"),
            (340, 305, "ЗДОРОВЬЕ"),
            (340, 395, "КОШЕЛЁК"),
        ]
        labels_right = [
            (675, 125, "ВРЕМЯ"),
            (675, 215, "ПОГОДА"),
            (675, 305, "СЫТОСТЬ"),
            (675, 395, "БАНК"),
        ]
        lbl_font = _load_font(15, bold=True)
        for lx, ly, ltxt in labels_left + labels_right:
            draw_bg.text((lx, ly), ltxt, fill=(138, 108, 96, 255), font=lbl_font, anchor="lm")
            draw_bg.line([(lx, ly + 44), (lx + 265, ly + 44)], fill=(175, 150, 140, 255), width=2)

        draw_bg.text((70, 468), "УРОВЕНЬ", fill=(138, 108, 96, 255), font=lbl_font, anchor="lm")
        draw_bg.line([(70, 524), (760, 524)], fill=(175, 150, 140, 255), width=2)
        draw_bg.ellipse([805, 420, 945, 540], outline=(138, 108, 96, 255), width=3)
        draw_bg.text((875, 480), "CRMP", fill=(120, 90, 78, 255), font=_load_font(22, bold=True), anchor="mm")

    photo_box = (68, 108, 292, 422)
    photo_w = photo_box[2] - photo_box[0]
    photo_h = photo_box[3] - photo_box[1]
    if avatar_bytes:
        try:
            av_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((photo_w, photo_h))
            canvas.paste(av_img, (photo_box[0], photo_box[1]), av_img)
        except Exception:
            avatar_bytes = None

    draw = ImageDraw.Draw(canvas)
    if not avatar_bytes:
        draw.rectangle(photo_box, fill=(226, 216, 211, 255), outline=(145, 118, 106, 255), width=2)
        draw.text(
            ((photo_box[0] + photo_box[2]) // 2, (photo_box[1] + photo_box[3]) // 2),
            "ФОТО",
            fill=(120, 94, 82, 255),
            font=_load_font(26, bold=True),
            anchor="mm",
        )

    parts_nick = str(p.get("name") or "Игрок_РФ").split("_", 1)
    first_name = parts_nick[0].upper() if parts_nick else "ИГРОК"
    last_name = parts_nick[1].upper() if len(parts_nick) > 1 and parts_nick[1] else "ГРАЖДАНИН"

    world_time, world_weather = get_world_time_and_weather()
    xp_cur = int(p.get("xp", 0))
    xp_req = max(100, int(p.get("lvl", 1)) * 100)
    lvl_line = f"{p.get('lvl', 1)} [{xp_cur} / {xp_req} XP]"

    val_font = _load_font(24, bold=True)
    lvl_font = _load_font(22, bold=True)
    dark_ink = (56, 40, 34, 255)

    draw.text((340, 152), last_name, fill=dark_ink, font=val_font, anchor="lm")
    draw.text((340, 242), first_name, fill=dark_ink, font=val_font, anchor="lm")
    draw.text((340, 332), f"{p.get('hp', 100)}%", fill=dark_ink, font=val_font, anchor="lm")
    draw.text((340, 422), format_rub(int(p.get("money", 0))), fill=dark_ink, font=val_font, anchor="lm")

    draw.text((675, 152), world_time, fill=dark_ink, font=val_font, anchor="lm")
    draw.text((675, 242), world_weather.upper(), fill=dark_ink, font=val_font, anchor="lm")
    draw.text((675, 332), f"{p.get('hunger', 100)}%", fill=dark_ink, font=val_font, anchor="lm")
    draw.text((675, 422), format_rub(int(p.get("bank", 0))), fill=dark_ink, font=val_font, anchor="lm")

    draw.text((70, 500), lvl_line, fill=dark_ink, font=lvl_font, anchor="lm")

    out = io.BytesIO()
    canvas.convert("RGB").save(out, format="PNG")
    return out.getvalue()


async def _fetch_user_avatar_bytes(bot: Bot, uid: int) -> bytes | None:
    try:
        photos = await bot.get_user_profile_photos(uid, limit=1)
        if photos and photos.photos and photos.photos[0]:
            best_photo = photos.photos[0][-1]
            buf = io.BytesIO()
            await bot.download(best_photo, destination=buf)
            return buf.getvalue()
    except Exception:
        pass
    return None


def get_family_by_id(fid: Any) -> dict[str, Any] | None:
    if not fid:
        return None
    f_key = str(fid)
    if f_key in families and isinstance(families[f_key], dict):
        return normalize_family(families[f_key], f_key)
    return None


def get_player_family(p: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    uid = int(p.get("tg_id", 0))
    fam_id = p.get("family_id")
    if fam_id and str(fam_id) in families and isinstance(families[str(fam_id)], dict):
        f_key = str(fam_id)
        fdata = normalize_family(families[f_key], f_key)
        if uid in fdata["members"] or fdata["owner_uid"] == uid:
            return f_key, fdata
        p["family_id"] = None
    for k, fdata in list(families.items()):
        if isinstance(fdata, dict):
            norm = normalize_family(fdata, str(k))
            if norm["owner_uid"] == uid or uid in norm["members"]:
                p["family_id"] = str(k)
                return str(k), norm
    return None, None


def get_family_member_rank(fdata: dict[str, Any], uid: int) -> str:
    if int(fdata.get("owner_uid", 0)) == int(uid):
        return "Глава"
    ranks_map = fdata.get("ranks") or {}
    custom = ranks_map.get(str(uid)) or ranks_map.get(uid)
    if custom:
        return str(custom)
    return "Участник"


def get_family_upgrade_cost(fdata: dict[str, Any]) -> int:
    lvl = max(1, int(fdata.get("level", 1)))
    return FAMILY_UPGRADE_BASE_COST * lvl


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

        if isinstance(event, Message) and uid is not None:
            state: FSMContext | None = data.get("state")
            cur_state = await state.get_state() if state else None
            if cur_state != RegistrationStates.waiting_nickname.state:
                p = get_player(uid, event.from_user.full_name if event.from_user else "")
                if not p.get("registered"):
                    if state:
                        await state.set_state(RegistrationStates.waiting_nickname)
                    await safe_answer(
                        event,
                        "🪪 <b>Регистрация гражданина</b>\n"
                        "Для начала игры придумайте и отправьте ваш ник в формате <code>Имя_Фамилия</code>.\n"
                        "Пример: <code>Никита_Шакуров</code>",
                        parse_mode="HTML",
                    )
                    return

        return await handler(event, data)


def main_kb(uid: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💵 Работа")],
        [KeyboardButton(text="🍔 Еда и отдых"), KeyboardButton(text="🏥 Больница")],
        [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="🏛 Фракции")],
        [KeyboardButton(text="🏢 Бизнесы"), KeyboardButton(text="🏠 Недвижимость")],
        [KeyboardButton(text="🚗 Автосалон"), KeyboardButton(text="👨‍👩‍👧‍👦 Семья")],
        [KeyboardButton(text="💨 Вейп"), KeyboardButton(text="🏆 Топ-10")],
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


@dp.message(RegistrationStates.waiting_nickname)
async def process_registration_nickname(message: Message, state: FSMContext):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    raw = (message.text or "").strip()

    if raw.startswith("/") and not raw.startswith("/start"):
        await safe_answer(
            message,
            "⚠️ Сначала завершите регистрацию: отправьте ник в формате <code>Имя_Фамилия</code> (например, <code>Никита_Шакуров</code>).",
            parse_mode="HTML",
        )
        return

    ok, res = validate_rp_nick(raw)
    if not ok:
        await safe_answer(message, f"⚠️ {res}", parse_mode="HTML")
        return

    if is_nick_taken(res, exclude_tg_id=uid):
        await safe_answer(
            message,
            f"❌ Ник <code>{esc(res)}</code> уже занят другим игроком. Введите другой вариант:",
            parse_mode="HTML",
        )
        return

    p["name"] = res
    p["registered"] = True
    if not p.get("reg_date"):
        p["reg_date"] = datetime.now().strftime("%d %B %Y г.")
    save_state()
    await state.clear()

    await safe_answer(
        message,
        f"✅ Добро пожаловать в область, <b>{esc(p['name'])}</b>!\n"
        f"Ваш игровой ID: <b><code>#{p['game_id']}</code></b> | Дата регистрации: <b>{esc(p['reg_date'])}</b>\n"
        f"Стартовый баланс: <b>{p['money']} ₽</b> | Уровень: <b>{p['lvl']}</b>\n\n"
        f"Совет: укажите возраст через <code>/setage &lt;18..90&gt;</code> и откройте профиль кнопкой <b>«👤 Профиль»</b>.",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )


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
        rows.append(
            [
                InlineKeyboardButton(text=f"📂 Тикет #{tid}", callback_data=f"sup_view:{tid}"),
                InlineKeyboardButton(text=f"💬 Дописать #{tid}", callback_data=f"sup_ureply:{tid}"),
                InlineKeyboardButton(text=f"🔒 Закрыть #{tid}", callback_data=f"sup_uclose:{tid}"),
            ]
        )
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
    ticket.setdefault("messages", []).append(
        {
            "from": "player",
            "name": str(p["name"]),
            "text": text_body[:1000],
        }
    )
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
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    cur = await state.get_state()
    if cur is None:
        await safe_answer(message, "Нет активного действия для отмены.", reply_markup=main_kb(uid))
        return
    if cur == RegistrationStates.waiting_nickname.state and not p.get("registered"):
        await safe_answer(
            message,
            "⚠️ Нельзя отменить первичную регистрацию. Введите ник в формате <code>Имя_Фамилия</code>.",
            parse_mode="HTML",
        )
        return
    await state.clear()
    await safe_answer(message, "Действие отменено.", reply_markup=main_kb(uid))


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
        kb_rows.append(
            [
                InlineKeyboardButton(text=f"🔒 Закрыть #{t['id']}", callback_data=f"tclose:{t['id']}"),
            ]
        )
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
    ticket.setdefault("messages", []).append(
        {
            "from": "staff",
            "name": f"{staff['name']} [{h_info['title']}]",
            "text": reply_text,
        }
    )
    save_state()

    target_uid = int(ticket["user_id"])
    reply_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"💬 Ответить в #{tid}", callback_data=f"sup_ureply:{tid}"),
                InlineKeyboardButton(text=f"🔒 Закрыть #{tid}", callback_data=f"sup_uclose:{tid}"),
            ]
        ]
    )
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

    t_uid = int(target["tg_id"])
    fac_key = target.get("faction", "none")
    if fac_key in FACTIONS:
        fac_name = FACTIONS[fac_key]["name"]
        rk = int(target.get("rank", 1))
        rk_title = get_faction_rank_title(fac_key, rk)
        fac_line = (
            f"🏛 Фракция: <b>{esc(fac_name)}</b> — <b>{esc(rk_title)}</b> "
            f"(<code>{rk}/13</code>, очки: <code>{target.get('faction_points', 0)}</code>, выговоров: <code>{target.get('f_warns', 0)}/3</code>)"
        )
    else:
        fac_line = "🏛 Фракция: <b>Гражданский</b>"

    fam_id, fam_data = get_player_family(target)
    if fam_id and fam_data:
        fam_line = (
            f"👨‍👩‍👧‍👦 Семья: <b>{esc(fam_data.get('name'))}</b> (<code>#{esc(fam_id)}</code>, "
            f"ранг: <b>{esc(get_family_member_rank(fam_data, t_uid))}</b>, общак: <b>{format_rub(int(fam_data.get('balance', 0)))}</b>)"
        )
    else:
        fam_line = "👨‍👩‍👧‍👦 Семья: <b>Не состоит</b>"

    age_txt = f"<b>{target['age']} лет</b>" if target.get("age") else "Не указан (/setage)"
    leader_tag = " 👑 Лидер" if target.get("leader_of") else ""
    rep_val = int(target.get("reputation", 0))
    rep_title = get_reputation_title(rep_val)
    xp_cur = int(target.get("xp", 0))
    xp_req = max(100, int(target.get("lvl", 1)) * 100)

    now = time.time()
    statuses: list[str] = []
    if target.get("banned"):
        statuses.append(f"🚫 Бан ({target.get('ban_reason') or 'причина не указана'})")
    tb_until = float(target.get("tempban_until", 0.0) or 0.0)
    if tb_until > now:
        statuses.append(f"⏳ Темпбан ({format_duration(tb_until - now)})")
    dm_until = float(target.get("dep_mute_until", 0.0) or 0.0)
    if dm_until > now:
        statuses.append(f"🔇 Мут /d ({format_duration(dm_until - now)})")
    if int(target.get("wanted", 0)) > 0:
        statuses.append(f"🚨 Розыск {target['wanted']}/6")
    if int(target.get("fines", 0)) > 0:
        statuses.append(f"🧾 Штрафы {format_rub(int(target['fines']))}")
    status_line = "\n📌 Статусы: " + " | ".join(esc(s) for s in statuses) if statuses else "\n📌 Статусы: <b>Чист</b>"

    a_lvl = get_admin_lvl(t_uid)
    h_lvl = int(target.get("helper_lvl", 0))
    m_lvl = get_media_lvl(t_uid)
    staff_line = ""
    if is_admin(uid, 1) or t_uid == uid:
        staff_line = (
            f"\n🛡 Админ: <b>{esc(get_admin_title(a_lvl))}</b> | 🛟 Хелпер: <b>{esc(get_helper_title(h_lvl))}</b> (<code>{target.get('helper_answers', 0)}</code> отв.)"
            f"\n🎬 Медиа: <b>{esc(get_media_title(m_lvl))}</b> (призов: <code>{target.get('media_prizes_given', 0)}</code>, промо: <code>{target.get('media_promos_created', 0)}</code>)"
        )

    vape_txt = (
        f"{esc(target['vape_name'])} (жижа: <code>{target['vape_liquid']}%</code>, акб: <code>{target['vape_battery']}%</code>, затяжек: <code>{target.get('vape_puffs', 0)}</code>)"
        if target.get("has_vape")
        else "Нет"
    )
    owned_biz = [b["name"] for b in businesses.values() if isinstance(b, dict) and b.get("owner_uid") == t_uid]
    biz_txt = ", ".join(esc(x) for x in owned_biz) if owned_biz else "Нет"
    cars_txt = ", ".join(esc(SHOP_CARS[c]["name"]) for c in target.get("cars", []) if c in SHOP_CARS) or "Нет"
    houses_txt = ", ".join(esc(SHOP_HOUSES[h]["name"]) for h in target.get("houses", []) if h in SHOP_HOUSES) or "Нет"
    total_cap = int(target["money"]) + int(target["bank"])

    await safe_answer(
        message,
        f"📋 <b>Досье гражданина: {esc(target['name'])}</b> (<code>#{target['game_id']}</code>){leader_tag}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Регистрация: <b>{esc(target.get('reg_date') or '—')}</b> | 🎂 Возраст: {age_txt}\n"
        f"🏆 Уровень: <b>{target['lvl']}</b> [<code>{xp_cur} / {xp_req} XP</code>]\n"
        f"📍 Репутация: <b><code>{rep_val}</code></b> · <i>{esc(rep_title)}</i>\n"
        f"👛 Кошелёк: <b>{esc(format_rub(int(target['money'])))}</b> | 🏦 Банк: <b>{esc(format_rub(int(target['bank'])))}</b>\n"
        f"💎 Общий капитал: <b>{esc(format_rub(total_cap))}</b>\n"
        f"❤️ Здоровье: <code>{target['hp']}/100</code> | 🍗 Сытость: <code>{target['hunger']}/100</code> | ⚡ Силы: <code>{target['stamina']}/100</code>\n"
        f"🎰 Казино: побед <code>{target['casino_wins']}</code> / поражений <code>{target['casino_losses']}</code>\n"
        f"{fac_line}\n"
        f"{fam_line}\n"
        f"💨 Вейп: {vape_txt}\n"
        f"🏢 Бизнесы: {biz_txt}\n"
        f"🚗 Авто: {cars_txt}\n"
        f"🏠 Недвижимость: {houses_txt}{status_line}{staff_line}",
        parse_mode="HTML",
    )


@dp.message(Command("d"))
async def cmd_department_radio(message: Message, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    rk = int(p.get("rank", 1))
    is_adm = is_admin(uid, 1)

    now = time.time()
    mute_until = float(p.get("dep_mute_until", 0.0) or 0.0)
    if mute_until > now and not is_creator(uid):
        await safe_answer(
            message,
            f"🔇 У вас действует мут рации департамента (/d).\n"
            f"Осталось: <b>{esc(format_duration(mute_until - now))}</b>.",
            parse_mode="HTML",
        )
        return
    if mute_until > 0 and mute_until <= now:
        p["dep_mute_until"] = 0.0
        save_state()

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
        broadcast = (
            f"📻 <b>[D] [{esc(FACTIONS[fid]['name'])}] {esc(rk_title)} "
            f"{esc(p['name'])} (<code>#{p['game_id']}</code>):</b> {esc(msg_body)}"
        )
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
    if not is_admin(uid, 3):
        await safe_answer(message, "⛔ Выдавать мут рации департамента можно с 3 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].lstrip("#").isdigit() or not parts[2].isdigit():
        await safe_answer(message, "Формат: <code>/dmute &lt;игровой_ID&gt; &lt;минуты&gt;</code> (0 — снять мут)", parse_mode="HTML")
        return
    gid = int(parts[1].lstrip("#"))
    mins = int(parts[2])
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return

    t_uid = int(target["tg_id"])
    t_key = str(t_uid)
    if mins <= 0:
        target["dep_mute_until"] = 0.0
        if t_key in users and isinstance(users[t_key], dict):
            users[t_key]["dep_mute_until"] = 0.0
        save_state()
        await safe_answer(message, f"🔊 Мут рации департамента снят с <b>{esc(target['name'])}</b> (<code>#{gid}</code>).", parse_mode="HTML")
        await safe_send(bot, t_uid, "🔊 С вас снят мут рации департамента (/d).", parse_mode="HTML")
        return

    until_ts = time.time() + mins * 60
    target["dep_mute_until"] = until_ts
    if t_key in users and isinstance(users[t_key], dict):
        users[t_key]["dep_mute_until"] = until_ts
    save_state()
    await safe_answer(
        message,
        f"🔇 Игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>) выдан мут /d на <b>{mins} мин.</b>",
        parse_mode="HTML",
    )
    await safe_send(bot, t_uid, f"🔇 Вам выдан мут рации департамента (/d) на <b>{mins} мин.</b>", parse_mode="HTML")


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)

    if not p.get("registered"):
        await state.set_state(RegistrationStates.waiting_nickname)
        await safe_answer(
            message,
            "🇷🇺 Добро пожаловать в <b>Criminal Russia RP</b>!\n\n"
            "Для создания паспорта гражданина введите ваш ник в формате <code>Имя_Фамилия</code>.\n"
            "Пример: <code>Никита_Шакуров</code>",
            parse_mode="HTML",
        )
        return

    await state.clear()
    age_txt = f"{p['age']} лет" if p.get("age") else "Не указан (/setage)"
    await safe_answer(
        message,
        f"🇷🇺 С возвращением в <b>Criminal Russia RP</b>!\n"
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
        "• <code>/start</code> — запуск, регистрация и обновление меню",
        "• <code>/setnick &lt;Имя_Фамилия&gt;</code> — сменить RP-ник (20 000 ₽)",
        "• <code>/setage &lt;18..90&gt;</code> — установить игровой возраст персонажа",
        "• <code>/info [ID или Ник]</code> — подробное досье игрока",
        "• <code>/vape</code> или кнопка «💨 Вейп» — покупка, заправка, зарядка и затяжки",
        "• <code>/d &lt;сообщение&gt;</code> — рация департамента (с 6/13 ранга госструктур)",
        "• <code>/pay &lt;ID&gt; &lt;сумма&gt;</code> — перевести деньги игроку (комиссия 3%)",
        "• <code>/bank put &lt;сумма&gt;</code> / <code>/bank take &lt;сумма&gt;</code> — операции с банком",
        "• <code>/work</code> — отработать смену (тратит выносливость и голод)",
        "• <code>/casino &lt;сумма&gt;</code> — сыграть в казино",
        "• <code>/heal</code> — пройти лечение в больнице",
        "• <code>/promo &lt;КОД&gt;</code> — активировать промокод",
        "• <code>/support &lt;текст&gt;</code> — написать в поддержку (или кнопка «🎫 Поддержка»)",
        "• <code>/members [фракция]</code> — состав фракции (13 званий, включая Суд)",
        "• <code>/r &lt;текст&gt;</code>, <code>/fapps</code>, <code>/faccept</code>, <code>/fdecline</code>, <code>/fdeposit</code>, <code>/fwarn</code> — фракции",
        "• <code>/createfam &lt;Название&gt;</code> или кнопка «👨‍👩‍👧‍👦 Семья» — создание и управление семьёй",
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
    if is_media(uid, 8) or is_admin(uid, 11):
        lines.append("• <code>/setmediarank &lt;ID&gt; &lt;0..8&gt;</code> — назначить ранг медиа (8 ранг медиа / админ 11+)")
    if is_admin(uid, 1):
        lines.extend(
            [
                "",
                f"🛡 <b>Администрация (ранги 1–{ADMIN_MAX_RANK}):</b>",
                f"• <code>/admins</code> — список администрации и ранги 1–{ADMIN_MAX_RANK}",
                "• <code>/players</code> — список игроков",
                "• <code>/changename &lt;ID&gt; &lt;Имя_Фамилия&gt;</code> — сменить ник игроку",
                "• <code>/addpromo &lt;КОД&gt; &lt;сумма&gt; &lt;активаций&gt;</code> — создать промокод",
                "• <code>/delpromo &lt;КОД&gt;</code> — удалить промокод",
                "• <code>/sethelper &lt;ID&gt; &lt;0..8&gt;</code> и <code>/helpers</code> — ранги хелперов (1–8)",
                "• <code>/setmedia &lt;ID&gt; &lt;0..8&gt;</code> — выдать или изменить ранг медиа (0 — снять)",
                f"• <code>/setadmin &lt;ID&gt; &lt;0..{ADMIN_MAX_RANK}&gt;</code> — выдать уровень админа",
                "• <code>/setleader &lt;ID&gt; &lt;фракция|none&gt;</code> — назначить лидера",
                "• <code>/dmute &lt;ID&gt; &lt;минуты&gt;</code> — мут рации департамента",
                "• <code>/ban &lt;ID&gt; [причина]</code> и <code>/unban &lt;ID&gt;</code>",
                "• <code>/tempban &lt;ID&gt; &lt;срок&gt; [причина]</code> и <code>/untempban &lt;ID&gt;</code>",
                "• <code>/resetplayer &lt;ID&gt;</code> и <code>/wipeall CONFIRM</code>",
            ]
        )
    await safe_answer(message, "\n".join(lines), reply_markup=main_kb(uid), parse_mode="HTML")


@dp.message(F.text == "👤 Профиль")
async def btn_profile(message: Message, bot: Bot):
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

    fam_id, fam_data = get_player_family(p)
    if fam_id and fam_data:
        fam_line = (
            f"👨‍👩‍👧‍👦 Семья: <b>{esc(fam_data.get('name'))}</b> (<code>#{esc(fam_id)}</code> · "
            f"<b>{esc(get_family_member_rank(fam_data, uid))}</b>)"
        )
    else:
        fam_line = "👨‍👩‍👧‍👦 Семья: <b>нет</b>"

    role_tag = " 👑 Лидер" if p.get("leader_of") else ""
    a_lvl = get_admin_lvl(uid)
    admin_line = f"\n🛡 Администрация: <b>{esc(get_admin_title(a_lvl))}</b>" if is_creator(uid) or a_lvl > 0 else ""
    h_lvl = int(p.get("helper_lvl", 0))
    helper_line = f"\n🛟 Хелперка: <b>{esc(get_helper_title(h_lvl))}</b> (ответов: <code>{p['helper_answers']}</code>)" if h_lvl > 0 else ""
    m_lvl = get_media_lvl(uid)
    media_line = f"\n🎬 Медиа: <b>{esc(get_media_title(m_lvl))}</b>" if m_lvl > 0 else ""
    vape_line = (
        f"\n💨 Вейп: <b>{esc(p['vape_name'])}</b> (жижа: <code>{p['vape_liquid']}%</code>, заряд: <code>{p['vape_battery']}%</code>)"
        if p.get("has_vape")
        else "\n💨 Вейп: <b>Нет</b>"
    )

    house_cnt = len(p.get("houses") or [])
    car_cnt = len(p.get("cars") or [])
    biz_cnt = sum(1 for b in businesses.values() if isinstance(b, dict) and b.get("owner_uid") == uid)
    inv_used = car_cnt + house_cnt + biz_cnt + (1 if p.get("has_vape") else 0)
    inv_total = 30

    age_txt = f"<b>{p['age']} лет</b>" if p.get("age") else "Не указан (/setage)"
    rep_val = int(p.get("reputation", 0))
    rep_title = get_reputation_title(rep_val)
    xp_cur = int(p.get("xp", 0))
    xp_req = max(100, int(p.get("lvl", 1)) * 100)

    caption = (
        f"👤 <b>Паспорт · РФ</b>\n"
        f"<b>{esc(p['name'])}</b> · ID <b><code>{p['game_id']}</code></b>\n"
        f"Регистрация: <i>{esc(p.get('reg_date') or '—')}</i>\n\n"
        f"🏆 Уровень: <b>{p['lvl']}</b> [<code>{xp_cur} / {xp_req} XP</code>]\n"
        f"🎂 Возраст: {age_txt}\n"
        f"📍 Репутация области: <b><code>{rep_val}</code></b> · <i>{esc(rep_title)}</i>\n"
        f"❤️ <code>{p['hp']}%</code> · 🍗 <code>{p['hunger']}%</code> · ⚡ <code>{p['stamina']}%</code>\n\n"
        f"🏠 Дома: <code>{house_cnt}</code> · 🚗 Авто: <code>{car_cnt}</code> · 🏢 Бизнесы: <code>{biz_cnt}/3</code>\n"
        f"{fam_line} · 🎒 <code>{inv_used}/{inv_total}</code>\n"
        f"{fac_line}{role_tag}{admin_line}{helper_line}{media_line}{vape_line}\n\n"
        f"<i>Подробности — в разделах ниже или в <code>/info</code>.</i>"
    )

    avatar_bytes = await _fetch_user_avatar_bytes(bot, uid)
    card_bytes = _build_passport_card_bytes(p, avatar_bytes=avatar_bytes)
    if card_bytes:
        photo = BufferedInputFile(card_bytes, filename=f"passport_{p['game_id']}.png")
        try:
            await message.answer_photo(photo=photo, caption=caption, reply_markup=main_kb(uid), parse_mode="HTML")
            return
        except Exception:
            pass

    await safe_answer(message, caption, reply_markup=main_kb(uid), parse_mode="HTML")


def render_vape_menu_kb(p: dict[str, Any]) -> InlineKeyboardMarkup:
    if not p.get("has_vape"):
        rows = [
            [
                InlineKeyboardButton(
                    text=f"🛒 {dev['name']} ({dev['price']} ₽)",
                    callback_data=f"vape_buy:{key}",
                )
            ]
            for key, dev in VAPE_DEVICES.items()
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💨 Затянуться", callback_data="vape_puff"),
                InlineKeyboardButton(text=f"💧 Жижа ({VAPE_REFILL_COST} ₽)", callback_data="vape_refill"),
            ],
            [
                InlineKeyboardButton(text=f"🔋 Зарядить ({VAPE_CHARGE_COST} ₽)", callback_data="vape_charge"),
                InlineKeyboardButton(text="🔄 Сменить устройство", callback_data="vape_shop"),
            ],
        ]
    )


@dp.message(Command("vape"))
@dp.message(F.text == "💨 Вейп")
async def cmd_vape(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    if not p.get("has_vape"):
        lines = [
            "💨 <b>Вейп-шоп «Cloud Russia»</b>\n"
            "У вас пока нет вейпа. Выберите устройство:\n"
        ]
        for dev in VAPE_DEVICES.values():
            lines.append(
                f"• <b>{esc(dev['name'])}</b> — <b>{dev['price']} ₽</b> "
                f"(<code>+{dev['stamina_bonus']}</code> сил, <code>+{dev['mood_xp']}</code> XP за затяжку)"
            )
        await safe_answer(
            message,
            "\n".join(lines),
            reply_markup=render_vape_menu_kb(p),
            parse_mode="HTML",
        )
        return

    await safe_answer(
        message,
        f"💨 <b>Ваш девайс: {esc(p.get('vape_name') or 'Pod-система')}</b>\n"
        f"• Уровень жидкости: <b><code>{p.get('vape_liquid', 0)}%</code></b>\n"
        f"• Заряд батареи: <b><code>{p.get('vape_battery', 0)}%</code></b>\n"
        f"• Всего затяжек: <b><code>{p.get('vape_puffs', 0)}</code></b>\n"
        f"• Наличные: <b>{p['money']} ₽</b>",
        reply_markup=render_vape_menu_kb(p),
        parse_mode="HTML",
    )


@dp.callback_query(F.data == "vape_shop")
async def cb_vape_shop(callback: CallbackQuery):
    uid = callback.from_user.id
    get_player(uid, callback.from_user.full_name)
    rows = [
        [
            InlineKeyboardButton(
                text=f"🛒 {dev['name']} ({dev['price']} ₽)",
                callback_data=f"vape_buy:{key}",
            )
        ]
        for key, dev in VAPE_DEVICES.items()
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад к девайсу", callback_data="vape_back")])
    if callback.message:
        try:
            await callback.message.edit_text(
                "💨 <b>Выберите новое устройство:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML",
            )
        except Exception:
            await safe_answer(callback.message, "💨 <b>Выберите новое устройство:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "vape_back")
async def cb_vape_back(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if callback.message:
        txt = (
            f"💨 <b>Ваш девайс: {esc(p.get('vape_name') or 'Pod-система')}</b>\n"
            f"• Уровень жидкости: <b><code>{p.get('vape_liquid', 0)}%</code></b>\n"
            f"• Заряд батареи: <b><code>{p.get('vape_battery', 0)}%</code></b>\n"
            f"• Всего затяжек: <b><code>{p.get('vape_puffs', 0)}</code></b>\n"
            f"• Наличные: <b>{p['money']} ₽</b>"
        )
        try:
            await callback.message.edit_text(txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")
        except Exception:
            await safe_answer(callback.message, txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("vape_buy:"))
async def cb_vape_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    key = callback.data.split(":", 1)[1]
    dev = VAPE_DEVICES.get(key)
    if not dev:
        await callback.answer("Устройство не найдено", show_alert=True)
        return
    price = int(dev["price"])
    if int(p["money"]) < price:
        await callback.answer(f"Не хватает наличных (нужно {price} ₽)", show_alert=True)
        return

    p["money"] = int(p["money"]) - price
    p["has_vape"] = True
    p["vape_key"] = key
    p["vape_name"] = dev["name"]
    p["vape_liquid"] = 100
    p["vape_battery"] = 100
    save_state()

    await callback.answer(f"Куплено: {dev['name']}!", show_alert=True)
    if callback.message:
        txt = (
            f"✅ Вы приобрели <b>{esc(dev['name'])}</b> за <b>{price} ₽</b>!\n"
            f"• Жидкость: <b><code>100%</code></b> | Батарея: <b><code>100%</code></b>"
        )
        try:
            await callback.message.edit_text(txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")
        except Exception:
            await safe_answer(callback.message, txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")


@dp.callback_query(F.data == "vape_puff")
async def cb_vape_puff(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not p.get("has_vape"):
        await callback.answer("Сначала купите вейп!", show_alert=True)
        return

    now = time.time()
    left = int(VAPE_PUFF_COOLDOWN - (now - float(p.get("last_vape_puff", 0.0) or 0.0)))
    if left > 0 and not is_creator(uid):
        await callback.answer(f"Подождите {left} сек. перед следующей затяжкой", show_alert=True)
        return

    liq = int(p.get("vape_liquid", 0))
    bat = int(p.get("vape_battery", 0))
    if liq < 8:
        await callback.answer("Закончилась жидкость! Заправьте картридж/бак.", show_alert=True)
        return
    if bat < 6:
        await callback.answer("Батарея разряжена! Поставьте устройство на зарядку.", show_alert=True)
        return

    dev = VAPE_DEVICES.get(str(p.get("vape_key") or ""), VAPE_DEVICES["pod_mini"])
    flavor = random.choice(VAPE_FLAVORS)
    liq_loss = random.randint(6, 10)
    bat_loss = random.randint(5, 9)

    p["vape_liquid"] = clamp_stat(liq - liq_loss)
    p["vape_battery"] = clamp_stat(bat - bat_loss)
    p["vape_puffs"] = int(p.get("vape_puffs", 0)) + 1
    p["last_vape_puff"] = now
    p["stamina"] = clamp_stat(int(p.get("stamina", 100)) + int(dev.get("stamina_bonus", 6)))
    p["xp"] = int(p.get("xp", 0)) + int(dev.get("mood_xp", 8))
    while p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1
    save_state()

    await callback.answer(
        f"Затяжка ({flavor})! Силы: {p['stamina']}/100 | Жижа: {p['vape_liquid']}% | Акб: {p['vape_battery']}%",
        show_alert=True,
    )
    if callback.message:
        txt = (
            f"💨 <b>Ваш девайс: {esc(p.get('vape_name') or 'Pod-система')}</b>\n"
            f"Последняя затяжка: <b>{esc(flavor)}</b> (<code>+{dev.get('mood_xp', 8)} XP</code>, <code>+{dev.get('stamina_bonus', 6)}</code> сил)\n"
            f"• Уровень жидкости: <b><code>{p['vape_liquid']}%</code></b>\n"
            f"• Заряд батареи: <b><code>{p['vape_battery']}%</code></b>\n"
            f"• Всего затяжек: <b><code>{p['vape_puffs']}</code></b>"
        )
        try:
            await callback.message.edit_text(txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")
        except Exception:
            pass


@dp.callback_query(F.data == "vape_refill")
async def cb_vape_refill(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not p.get("has_vape"):
        await callback.answer("У вас нет вейпа", show_alert=True)
        return
    if int(p.get("vape_liquid", 0)) >= 100:
        await callback.answer("Жидкость уже заправлена на 100%", show_alert=True)
        return
    if int(p["money"]) < VAPE_REFILL_COST:
        await callback.answer(f"Нужно {VAPE_REFILL_COST} ₽ на жидкость", show_alert=True)
        return

    p["money"] = int(p["money"]) - VAPE_REFILL_COST
    p["vape_liquid"] = 100
    save_state()
    await callback.answer(f"Жидкость заправлена до 100% (-{VAPE_REFILL_COST} ₽)", show_alert=True)
    if callback.message:
        txt = (
            f"💨 <b>Ваш девайс: {esc(p.get('vape_name') or 'Pod-система')}</b>\n"
            f"• Уровень жидкости: <b><code>100%</code></b>\n"
            f"• Заряд батареи: <b><code>{p['vape_battery']}%</code></b>\n"
            f"• Наличные: <b>{p['money']} ₽</b>"
        )
        try:
            await callback.message.edit_text(txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")
        except Exception:
            pass


@dp.callback_query(F.data == "vape_charge")
async def cb_vape_charge(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if not p.get("has_vape"):
        await callback.answer("У вас нет вейпа", show_alert=True)
        return
    if int(p.get("vape_battery", 0)) >= 100:
        await callback.answer("Батарея уже заряжена на 100%", show_alert=True)
        return
    if int(p["money"]) < VAPE_CHARGE_COST:
        await callback.answer(f"Нужно {VAPE_CHARGE_COST} ₽ на зарядку", show_alert=True)
        return

    p["money"] = int(p["money"]) - VAPE_CHARGE_COST
    p["vape_battery"] = 100
    save_state()
    await callback.answer(f"Батарея заряжена до 100% (-{VAPE_CHARGE_COST} ₽)", show_alert=True)
    if callback.message:
        txt = (
            f"💨 <b>Ваш девайс: {esc(p.get('vape_name') or 'Pod-система')}</b>\n"
            f"• Уровень жидкости: <b><code>{p['vape_liquid']}%</code></b>\n"
            f"• Заряд батареи: <b><code>100%</code></b>\n"
            f"• Наличные: <b>{p['money']} ₽</b>"
        )
        try:
            await callback.message.edit_text(txt, reply_markup=render_vape_menu_kb(p), parse_mode="HTML")
        except Exception:
            pass


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
    p["registered"] = True
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
    if not is_admin(uid, 7):
        await safe_answer(message, "⛔ Принудительно менять ники игрокам можно с 7 ранга администратора.")
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
    target["registered"] = True
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
    if not (is_admin(uid, 7) or spec is not None):
        await safe_answer(message, "⛔ Создавать промокоды можно с 7 ранга администратора или с ролью медиа.")
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
    if not is_admin(uid, 7) and spec is not None:
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
    if not is_admin(uid, 7):
        await safe_answer(message, "⛔ Удалять промокоды можно с 7 ранга администратора.")
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
        if not is_admin(uid, 6):
            await safe_answer(message, "⛔ Просматривать состав любой фракции можно с 6 ранга администратора.")
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
            kb_rows.append(
                [
                    InlineKeyboardButton(text=f"💰 Собрать ({pending} ₽)", callback_data=f"biz_take:{bid}"),
                    InlineKeyboardButton(text=f"🏷 Продать ({refund} ₽)", callback_data=f"biz_sell:{bid}"),
                ]
            )
        elif owner_uid is None:
            lines.append(f"• <b>{esc(b['name'])}</b> — цена <b>{b['price']} ₽</b>, доход <code>{income_hr} ₽/ч</code> <i>(Свободен)</i>")
            kb_rows.append(
                [
                    InlineKeyboardButton(text=f"🛒 Купить {b['name']}", callback_data=f"biz_buy:{bid}")
                ]
            )
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
    get_player(uid, message.from_user.full_name)
    actor_m_lvl = get_media_lvl(uid)
    can_manage = is_admin(uid, 11) or (actor_m_lvl >= 8)
    if not can_manage:
        await safe_answer(message, "⛔ Назначать ранги медиа могут админы 11+ ранга или Руководитель медиа-отдела (8 ранг).")
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

    if not is_admin(uid, 11) and lvl >= actor_m_lvl:
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
    manage_hint = "\n• <code>/setmediarank &lt;ID&gt; &lt;0..8&gt;</code> — назначение рангов медиа" if (is_admin(uid, 11) or m_lvl >= 8) else ""
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
    lines = [f"🛡 <b>Иерархия администрации (1–{ADMIN_MAX_RANK}):</b>\n" + ranks_list + "\n\n📋 <b>Текущий состав:</b>"]
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
    can_manage = is_admin(uid, 11) or int(actor.get("helper_lvl", 0)) >= 7
    if not can_manage:
        await safe_answer(message, "⛔ Назначать хелперов могут админы 11+ ранга или кураторы хелперов (7–8 ранг).")
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
    if not is_admin(uid, 11) and lvl >= int(actor.get("helper_lvl", 0)):
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
    if not is_admin(uid, 11):
        await safe_answer(message, "⛔ Выдавать и менять ранги медиа можно с 11 ранга администратора.")
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
    if not (is_creator(uid) or actor_lvl >= 13):
        await safe_answer(message, "⛔ Назначать администраторов можно с 13 ранга администратора или создателю.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        ranks_preview = "\n".join(f"• <code>{k}</code> — <b>{esc(v['title'])}</b>" for k, v in ADMIN_RANKS.items())
        await safe_answer(
            message,
            f"Формат: <code>/setadmin &lt;игровой_ID&gt; &lt;0..{ADMIN_MAX_RANK}&gt;</code>\n\n<b>Ранги администрации:</b>\n{ranks_preview}",
            parse_mode="HTML",
        )
        return
    try:
        gid = int(parts[1])
        lvl = int(parts[2])
    except ValueError:
        await safe_answer(message, "ID и уровень должны быть числами.")
        return
    if not (0 <= lvl <= ADMIN_MAX_RANK):
        await safe_answer(message, f"Уровень администратора должен быть от 0 до {ADMIN_MAX_RANK}.")
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
    if not is_admin(uid, 5):
        await safe_answer(message, "⛔ Банить игроков можно с 5 ранга администратора.")
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
    if not is_admin(uid, 5):
        await safe_answer(message, "⛔ Разбанивать игроков можно с 5 ранга администратора.")
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
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Выдавать временные баны можно с 4 ранга администратора.")
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
    if not is_admin(uid, 4):
        await safe_answer(message, "⛔ Снимать временные баны можно с 4 ранга администратора.")
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
            rows.append(
                [
                    InlineKeyboardButton(text=f"🏷 Продать {h['name']} ({refund} ₽)", callback_data=f"house_sell:{hid}")
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(text=f"🛒 Купить {h['name']}", callback_data=f"house_buy:{hid}")
                ]
            )
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
            rows.append(
                [
                    InlineKeyboardButton(text=f"🏷 Продать {c['name']} ({refund} ₽)", callback_data=f"car_sell:{cid}")
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(text=f"🛒 Купить {c['name']}", callback_data=f"car_buy:{cid}")
                ]
            )
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


def render_family_card_text(fid: str, fdata: dict[str, Any], uid: int) -> str:
    norm = normalize_family(fdata, fid)
    members = norm["members"]
    max_members = int(norm["max_members"])
    cars = norm["cars"]
    max_cars = int(norm["max_cars"])
    weapons = norm["weapons"]
    tokens = int(norm["tokens"])
    rep = int(norm["reputation"])
    contracts_done = int(norm["contracts_done"])
    your_rank = get_family_member_rank(norm, uid)
    upg_cost = get_family_upgrade_cost(norm)
    mansion_txt = norm["mansion_name"] if norm["has_mansion"] else "нет"
    tanker_txt = f"{norm['tanker_fuel']} л." if norm["tanker_fuel"] > 0 else "пусто"
    wh_txt = f"{norm['warehouse_items']} шт." if norm["warehouse_items"] > 0 else "пусто"

    member_lines = []
    for m_uid in members[:12]:
        m_u = users.get(str(m_uid))
        m_name = str(m_u.get("name")) if isinstance(m_u, dict) and m_u.get("name") else f"Игрок_{m_uid}"
        m_rk = get_family_member_rank(norm, m_uid)
        member_lines.append(f"• {esc(m_name)} · {esc(m_rk)}")

    cars_txt = ", ".join(esc(SHOP_CARS[c]["name"] if c in SHOP_CARS else c) for c in cars) if cars else "<i>пусто</i>"
    weapons_txt = (
        ", ".join(esc(FAMILY_WEAPONS[w]["name"] if w in FAMILY_WEAPONS else w) for w in weapons)
        if weapons
        else "<i>пусто · купить в арсенале семьи</i>"
    )

    return (
        f"👨‍👩‍👧‍👦 <b>Семья «{esc(norm['name'])}»</b> (ур. <code>{norm['level']}</code>)\n"
        f"👥 Состав: <code>{len(members)}/{max_members}</code>\n"
        f"🚗 Автопарк: <code>{len(cars)}/{max_cars}</code>\n"
        f"🔫 Арсенал: <code>{len(weapons)}</code>\n"
        f"🪙 Семейные жетоны: <code>{tokens}</code>\n"
        f"🏅 Репутация: <code>{rep}</code>\n"
        f"📋 Контракты сегодня: <code>{contracts_done}/{FAMILY_DAILY_CONTRACTS_LIMIT}</code>\n"
        f"🎖 Ваш ранг: <b>{esc(your_rank)}</b>\n"
        f"⬆️ Апгрейд: <b>{esc(format_rub(upg_cost))}</b>\n"
        f"🏦 Казна семьи: <b>{esc(format_rub(int(norm['balance'])))}</b>\n\n"
        f"👥 <b>Участники</b>\n"
        + ("\n".join(member_lines) if member_lines else "• <i>нет</i>")
        + f"\n\n🚗 <b>Автопарк</b>\n{cars_txt}\n\n"
        f"🔫 <b>Оружие</b>\n"
        f"<i>{weapons_txt}</i>\n"
        f"<i>Казна расходуется только на общий особняк, транспорт и арсенал; вывода денег нет.</i>\n"
        f"🏠 Особняк: <b>{esc(mansion_txt)}</b> | 📦 Склад: <code>{esc(wh_txt)}</code> | 🛢 Танкер: <code>{esc(tanker_txt)}</code>"
    )


def render_family_menu_kb(fid: str, fdata: dict[str, Any], uid: int) -> InlineKeyboardMarkup:
    is_owner = int(fdata.get("owner_uid", 0)) == int(uid)
    rows = [
        [
            InlineKeyboardButton(text="✉️ Пригласить", callback_data=f"fam_inv_ask:{fid}"),
            InlineKeyboardButton(text="⬆️ Апгрейд", callback_data=f"fam_upg:{fid}"),
            InlineKeyboardButton(text="💰 Казна", callback_data=f"fam_dep_ask:{fid}"),
        ],
        [
            InlineKeyboardButton(text="🏠 Особняк", callback_data=f"fam_mansion:{fid}"),
            InlineKeyboardButton(text="🚗 Автопарк", callback_data=f"fam_cars:{fid}"),
            InlineKeyboardButton(text="🔫 Арсенал", callback_data=f"fam_armory:{fid}"),
        ],
        [
            InlineKeyboardButton(text="📋 Контракт", callback_data=f"fam_contract:{fid}"),
            InlineKeyboardButton(text="📦 Склад", callback_data=f"fam_wh:{fid}"),
            InlineKeyboardButton(text="🛒 Магазин с.", callback_data=f"fam_shop:{fid}"),
        ],
        [
            InlineKeyboardButton(text="🏆 Рейтинг", callback_data="fam_rating"),
            InlineKeyboardButton(text="🛢 Танкер", callback_data=f"fam_tanker:{fid}"),
        ],
        [
            InlineKeyboardButton(text="🎖 Ранги", callback_data=f"fam_ranks:{fid}"),
            InlineKeyboardButton(text="👥 Состав", callback_data=f"fam_roster:{fid}"),
            InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"fam_rename_ask:{fid}"),
        ],
    ]
    if is_owner:
        rows.append([InlineKeyboardButton(text="🗑 Распустить семью", callback_data=f"fam_disband:{fid}")])
    else:
        rows.append([InlineKeyboardButton(text="🚪 Покинуть семью", callback_data=f"fam_leave:{fid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_or_edit_family_card(message: Message, fid: str, uid: int, edit: bool = False) -> None:
    fdata = get_family_by_id(fid)
    if not fdata:
        await safe_answer(message, "❌ Семья не найдена.", reply_markup=main_kb(uid))
        return
    txt = render_family_card_text(fid, fdata, uid)
    kb = render_family_menu_kb(fid, fdata, uid)
    if edit:
        try:
            await message.edit_text(txt, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await safe_answer(message, txt, reply_markup=kb, parse_mode="HTML")


@dp.message(F.text == "👨‍👩‍👧‍👦 Семья")
async def btn_family(message: Message, state: FSMContext):
    uid = message.from_user.id
    await state.clear()
    p = get_player(uid, message.from_user.full_name)
    fid, fdata = get_player_family(p)
    if not fid or not fdata:
        await safe_answer(
            message,
            "👨‍👩‍👧‍👦 <b>Семьи</b>\n"
            "Вы пока не состоите в семье.\n"
            f"Создать семью (стоимость <code>{format_rub(FAMILY_CREATE_COST)}</code>): <code>/createfam &lt;Название&gt;</code>",
            reply_markup=main_kb(uid),
            parse_mode="HTML",
        )
        return
    save_state()
    await send_or_edit_family_card(message, fid, uid, edit=False)


@dp.message(Command("createfam"))
async def cmd_createfam(message: Message, state: FSMContext):
    uid = message.from_user.id
    await state.clear()
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
    if int(p["money"]) < FAMILY_CREATE_COST:
        await safe_answer(
            message,
            f"Для создания семьи нужно <b>{esc(format_rub(FAMILY_CREATE_COST))}</b> наличными.",
            parse_mode="HTML",
        )
        return

    new_id = str(len(families) + 1)
    while new_id in families:
        new_id = str(int(new_id) + 1)

    p["money"] = int(p["money"]) - FAMILY_CREATE_COST
    p["family_id"] = new_id
    families[new_id] = normalize_family(
        {
            "id": new_id,
            "name": fam_name,
            "owner_uid": uid,
            "owner_name": p["name"],
            "members": [uid],
            "balance": 0,
            "tokens": 1,
            "reputation": 10,
        },
        new_id,
    )
    save_state()
    await safe_answer(
        message,
        f"🎉 Семья <b>«{esc(fam_name)}»</b> (<code>#{esc(new_id)}</code>) создана!",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )
    await send_or_edit_family_card(message, new_id, uid, edit=False)


@dp.callback_query(F.data.startswith("fam_inv_ask:"))
async def cb_fam_inv_ask(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata or int(fdata["owner_uid"]) != uid:
        await callback.answer("Приглашать участников может только Глава семьи", show_alert=True)
        return
    if len(fdata["members"]) >= int(fdata["max_members"]):
        await callback.answer("Достигнут лимит участников! Сделайте апгрейд семьи.", show_alert=True)
        return
    await state.update_data(fam_target_id=fid)
    await state.set_state(FamilyStates.inviting_member)
    await callback.answer()
    if callback.message:
        await safe_answer(
            callback.message,
            "✉️ Введите <b>игровой ID</b> игрока (например, <code>102</code>) для приглашения в семью (или <code>/cancel</code>):",
            parse_mode="HTML",
        )


@dp.message(FamilyStates.inviting_member)
async def process_fam_invite(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    raw = (message.text or "").strip().lstrip("#")
    data = await state.get_data()
    fid = str(data.get("fam_target_id") or "")
    await state.clear()

    fdata = get_family_by_id(fid)
    if not fdata or int(fdata["owner_uid"]) != uid:
        await safe_answer(message, "❌ Недостаточно прав для приглашения.", reply_markup=main_kb(uid))
        return
    if not raw.isdigit():
        await safe_answer(message, "⚠️ Укажите числовой игровой ID игрока.", reply_markup=main_kb(uid))
        return

    target = find_player_by_game_id(int(raw))
    if not target:
        await safe_answer(message, f"❌ Игрок <code>#{raw}</code> не найден.", reply_markup=main_kb(uid), parse_mode="HTML")
        return

    t_uid = int(target["tg_id"])
    t_fid, _ = get_player_family(target)
    if t_fid:
        await safe_answer(message, "⚠️ Этот игрок уже состоит в семье.", reply_markup=main_kb(uid))
        return
    if len(fdata["members"]) >= int(fdata["max_members"]):
        await safe_answer(message, "⚠️ В семье нет свободных мест. Улучшите семью через «⬆️ Апгрейд».", reply_markup=main_kb(uid))
        return

    fdata["members"].append(t_uid)
    target["family_id"] = fid
    save_state()

    await safe_answer(
        message,
        f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{raw}</code>) принят в семью <b>«{esc(fdata['name'])}»</b>!",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )
    await safe_send(
        bot,
        t_uid,
        f"👨‍👩‍👧‍👦 Вас пригласили и приняли в семью <b>«{esc(fdata['name'])}»</b>! Нажмите «👨‍👩‍👧‍👦 Семья» для просмотра.",
        parse_mode="HTML",
    )


@dp.callback_query(F.data.startswith("fam_upg:"))
async def cb_fam_upg(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if int(fdata["owner_uid"]) != uid:
        await callback.answer("Улучшать семью может только Глава", show_alert=True)
        return

    cost = get_family_upgrade_cost(fdata)
    if int(fdata["balance"]) < cost:
        await callback.answer(f"В казне семьи нужно {format_rub(cost)} (сейчас {format_rub(int(fdata['balance']))})", show_alert=True)
        return

    fdata["balance"] = int(fdata["balance"]) - cost
    fdata["level"] = int(fdata["level"]) + 1
    fdata["max_members"] = int(fdata["max_members"]) + 4
    fdata["max_cars"] = int(fdata["max_cars"]) + 2
    fdata["reputation"] = int(fdata["reputation"]) + 30
    save_state()

    await callback.answer(f"Семья улучшена до {fdata['level']} уровня!", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data.startswith("fam_dep_ask:"))
async def cb_fam_dep_ask(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata or int(p.get("tg_id", 0)) not in fdata["members"]:
        await callback.answer("Вы не состоите в этой семье", show_alert=True)
        return
    await state.update_data(fam_target_id=fid)
    await state.set_state(FamilyStates.depositing_treasury)
    await callback.answer()
    if callback.message:
        await safe_answer(
            callback.message,
            f"💰 Введите сумму для пополнения казны семьи (наличные: <b>{p['money']} ₽</b>) или <code>/cancel</code>:",
            parse_mode="HTML",
        )


@dp.message(FamilyStates.depositing_treasury)
async def process_fam_deposit(message: Message, state: FSMContext):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    raw = (message.text or "").strip().replace(" ", "")
    data = await state.get_data()
    fid = str(data.get("fam_target_id") or "")
    await state.clear()

    fdata = get_family_by_id(fid)
    if not fdata or uid not in fdata["members"]:
        await safe_answer(message, "❌ Семья не найдена.", reply_markup=main_kb(uid))
        return
    if not raw.isdigit():
        await safe_answer(message, "⚠️ Введите сумму числом.", reply_markup=main_kb(uid))
        return
    amount = int(raw)
    if amount < 500 or amount > 50_000_000:
        await safe_answer(message, "⚠️ Сумма пополнения — от <code>500 ₽</code> до <code>50 000 000 ₽</code>.", reply_markup=main_kb(uid), parse_mode="HTML")
        return
    if int(p["money"]) < amount:
        await safe_answer(message, f"💸 Недостаточно наличных (у вас <b>{p['money']} ₽</b>).", reply_markup=main_kb(uid), parse_mode="HTML")
        return

    p["money"] = int(p["money"]) - amount
    fdata["balance"] = int(fdata["balance"]) + amount
    save_state()

    await safe_answer(
        message,
        f"✅ Казна семьи <b>«{esc(fdata['name'])}»</b> пополнена на <b>{esc(format_rub(amount))}</b>!",
        reply_markup=main_kb(uid),
        parse_mode="HTML",
    )
    await send_or_edit_family_card(message, fid, uid, edit=False)


@dp.callback_query(F.data.startswith("fam_mansion:"))
async def cb_fam_mansion(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if fdata["has_mansion"]:
        await callback.answer(f"Особняк семьи уже куплен: {fdata['mansion_name']}", show_alert=True)
        return
    if int(fdata["owner_uid"]) != uid:
        await callback.answer("Купить особняк может только Глава семьи", show_alert=True)
        return
    price = 1_500_000
    if int(fdata["balance"]) < price:
        await callback.answer(f"В казне нужно {format_rub(price)} для покупки особняка", show_alert=True)
        return
    fdata["balance"] = int(fdata["balance"]) - price
    fdata["has_mansion"] = True
    fdata["reputation"] = int(fdata["reputation"]) + 50
    save_state()
    await callback.answer("Куплен общий особняк семьи (+50 репутации)!", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data.startswith("fam_cars:"))
async def cb_fam_cars(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if int(fdata["owner_uid"]) != uid:
        await callback.answer("Покупать авто в автопарк семьи может только Глава", show_alert=True)
        return
    if len(fdata["cars"]) >= int(fdata["max_cars"]):
        await callback.answer("Автопарк семьи заполнен! Сделайте апгрейд.", show_alert=True)
        return
    car_key = "vaz_2107" if len(fdata["cars"]) == 0 else "priora"
    cinfo = SHOP_CARS[car_key]
    price = int(cinfo["price"])
    if int(fdata["balance"]) < price:
        await callback.answer(f"В казне семьи нужно {format_rub(price)} для покупки {cinfo['name']}", show_alert=True)
        return
    fdata["balance"] = int(fdata["balance"]) - price
    fdata["cars"].append(car_key)
    save_state()
    await callback.answer(f"В автопарк семьи добавлен {cinfo['name']}!", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data.startswith("fam_armory:"))
async def cb_fam_armory(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if int(fdata["owner_uid"]) != uid:
        await callback.answer("Пополнять арсенал семьи может только Глава", show_alert=True)
        return
    winfo = FAMILY_WEAPONS["makarov"]
    price = int(winfo["price"])
    if int(fdata["balance"]) < price:
        await callback.answer(f"В казне семьи нужно {format_rub(price)} для покупки {winfo['name']}", show_alert=True)
        return
    fdata["balance"] = int(fdata["balance"]) - price
    fdata["weapons"].append("makarov")
    fdata["reputation"] = int(fdata["reputation"]) + int(winfo["rep_bonus"])
    save_state()
    await callback.answer(f"В арсенал добавлен: {winfo['name']}!", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data.startswith("fam_contract:"))
async def cb_fam_contract(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata or uid not in fdata["members"]:
        await callback.answer("Вы не состоите в этой семье", show_alert=True)
        return
    if int(fdata["contracts_done"]) >= FAMILY_DAILY_CONTRACTS_LIMIT:
        await callback.answer(f"Дневной лимит контрактов ({FAMILY_DAILY_CONTRACTS_LIMIT}/{FAMILY_DAILY_CONTRACTS_LIMIT}) исчерпан", show_alert=True)
        return
    fdata["contracts_done"] = int(fdata["contracts_done"]) + 1
    fdata["tokens"] = int(fdata["tokens"]) + 2
    fdata["reputation"] = int(fdata["reputation"]) + 15
    fdata["balance"] = int(fdata["balance"]) + 45000
    save_state()
    await callback.answer("Контракт выполнен! +2 жетона, +15 репутации, +45 000 ₽ в казну", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data.startswith("fam_wh:"))
async def cb_fam_wh(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    await callback.answer(
        f"Склад семьи: {fdata['warehouse_items']} шт. | Танкер: {fdata['tanker_fuel']} л.",
        show_alert=True,
    )


@dp.callback_query(F.data.startswith("fam_shop:"))
async def cb_fam_shop(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if int(fdata["owner_uid"]) != uid:
        await callback.answer("Закупать припасы для семьи может только Глава", show_alert=True)
        return
    cost = 50000
    if int(fdata["balance"]) < cost:
        await callback.answer(f"В казне нужно {format_rub(cost)} для закупки припасов", show_alert=True)
        return
    fdata["balance"] = int(fdata["balance"]) - cost
    fdata["warehouse_items"] = int(fdata["warehouse_items"]) + 10
    fdata["tanker_fuel"] = int(fdata["tanker_fuel"]) + 100
    save_state()
    await callback.answer("Закуплено +10 припасов на склад и +100 л. топлива в танкер!", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data == "fam_rating")
async def cb_fam_rating(callback: CallbackQuery):
    top = []
    for k, fdata in families.items():
        if isinstance(fdata, dict):
            norm = normalize_family(fdata, str(k))
            top.append((int(norm["reputation"]), int(norm["level"]), str(norm["name"]), str(k)))
    top.sort(key=lambda x: (-x[0], -x[1]))
    if not top:
        await callback.answer("Рейтинг семей пока пуст", show_alert=True)
        return
    summary = " | ".join(f"{i+1}. {name} ({rep} реп.)" for i, (rep, _, name, _) in enumerate(top[:5]))
    await callback.answer(f"Топ семей: {summary}", show_alert=True)


@dp.callback_query(F.data.startswith("fam_tanker:"))
async def cb_fam_tanker(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    if int(fdata["tanker_fuel"]) < 20:
        await callback.answer("В танкере недостаточно топлива (нужно минимум 20 л.)", show_alert=True)
        return
    fdata["tanker_fuel"] = int(fdata["tanker_fuel"]) - 20
    fdata["reputation"] = int(fdata["reputation"]) + 5
    save_state()
    await callback.answer("Выдан топливный бонус автопарку (-20 л., +5 репутации)", show_alert=True)
    if callback.message:
        await send_or_edit_family_card(callback.message, fid, uid, edit=True)


@dp.callback_query(F.data.startswith("fam_ranks:"))
async def cb_fam_ranks(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    rk_summary = ", ".join(
        f"{(users.get(str(m), {}) or {}).get('name', f'#{m}')}: {get_family_member_rank(fdata, m)}"
        for m in fdata["members"][:6]
    )
    await callback.answer(f"Ранги: {rk_summary}", show_alert=True)


@dp.callback_query(F.data.startswith("fam_roster:"))
async def cb_fam_roster(callback: CallbackQuery):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata:
        await callback.answer("Семья не найдена", show_alert=True)
        return
    names = [
        f"{(users.get(str(m), {}) or {}).get('name', f'#{m}')} ({get_family_member_rank(fdata, m)})"
        for m in fdata["members"][:8]
    ]
    await callback.answer(f"Состав ({len(fdata['members'])}/{fdata['max_members']}): " + ", ".join(names), show_alert=True)


@dp.callback_query(F.data.startswith("fam_rename_ask:"))
async def cb_fam_rename_ask(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata or int(fdata["owner_uid"]) != uid:
        await callback.answer("Переименовывать семью может только Глава", show_alert=True)
        return
    await state.update_data(fam_target_id=fid)
    await state.set_state(FamilyStates.renaming_family)
    await callback.answer()
    if callback.message:
        await safe_answer(callback.message, "✏️ Введите новое название семьи (до 32 символов) или <code>/cancel</code>:", parse_mode="HTML")


@dp.message(FamilyStates.renaming_family)
async def process_fam_rename(message: Message, state: FSMContext):
    uid = message.from_user.id
    new_name = (message.text or "").strip()[:32]
    data = await state.get_data()
    fid = str(data.get("fam_target_id") or "")
    await state.clear()

    fdata = get_family_by_id(fid)
    if not fdata or int(fdata["owner_uid"]) != uid:
        await safe_answer(message, "❌ Недостаточно прав.", reply_markup=main_kb(uid))
        return
    if len(new_name) < 2:
        await safe_answer(message, "⚠️ Название слишком короткое.", reply_markup=main_kb(uid))
        return

    fdata["name"] = new_name
    save_state()
    await safe_answer(message, f"✅ Семья переименована в <b>«{esc(new_name)}»</b>!", reply_markup=main_kb(uid), parse_mode="HTML")
    await send_or_edit_family_card(message, fid, uid, edit=False)


@dp.callback_query(F.data.startswith("fam_leave:"))
async def cb_fam_leave(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata or int(fdata["owner_uid"]) == uid:
        await callback.answer("Глава не может просто покинуть семью — используйте «Распустить семью»", show_alert=True)
        return
    if uid in fdata["members"]:
        fdata["members"].remove(uid)
    p["family_id"] = None
    save_state()
    await callback.answer("Вы покинули семью", show_alert=True)
    if callback.message:
        await safe_answer(callback.message, "🚪 Вы вышли из семьи.", reply_markup=main_kb(uid))


@dp.callback_query(F.data.startswith("fam_disband:"))
async def cb_fam_disband(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = get_family_by_id(fid)
    if not fdata or int(fdata["owner_uid"]) != uid:
        await callback.answer("Распустить семью может только Глава", show_alert=True)
        return
    for m_uid in list(fdata.get("members") or []):
        m_u = users.get(str(m_uid))
        if isinstance(m_u, dict):
            m_u["family_id"] = None
    p["family_id"] = None
    families.pop(fid, None)
    save_state()
    await callback.answer("Семья распущена", show_alert=True)
    if callback.message:
        await safe_answer(callback.message, "🗑 Семья распущена.", reply_markup=main_kb(uid))


@dp.message(F.text == "🏆 Топ-10")
async def btn_top10(message: Message):
    uid = message.from_user.id
    get_player(uid, message.from_user.full_name)
    ranked = []
    for k, u in users.items():
        if isinstance(u, dict):
            try:
                tg_id = int(u.get("tg_id") or k)
            except ValueError:
                continue
            norm = normalize_player(u, tg_id)
            cap = int(norm.get("money", 0)) + int(norm.get("bank", 0))
            ranked.append((cap, int(norm.get("lvl", 1)), str(norm.get("name", "Игрок")), int(norm.get("game_id", 0))))
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    lines = ["🏆 <b>Топ-10 самых состоятельных жителей области:</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    for idx, (cap, lvl, uname, gid) in enumerate(ranked[:10], start=1):
        prefix = medals[idx - 1] if idx <= 3 else f"<b>{idx}.</b>"
        lines.append(f"{prefix} <b>{esc(uname)}</b> (<code>#{gid}</code>) — <b>{cap} ₽</b> (<code>{lvl} ур.</code>)")
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


@dp.message(F.text == "🏛 Фракции")
async def btn_factions(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    cur_f = p.get("faction", "none")
    cur_line = (
        f"Ваша фракция: <b>{esc(FACTIONS[cur_f]['name'])}</b> — <b>{esc(get_faction_rank_title(cur_f, int(p['rank'])))}</b> (<code>{p['rank']}/13</code>)\n"
        if cur_f in FACTIONS
        else "Вы сейчас гражданский.\n"
    )
    lines = [f"🏛 <b>Государственные и криминальные фракции:</b>\n{cur_line}"]
    rows: list[list[InlineKeyboardButton]] = []
    for fid, fdata in FACTIONS.items():
        fs = get_fstate(fid)
        lines.append(
            f"• <b>{esc(fdata['name'])}</b> (<code>{fid}</code>) — оклад <code>{fdata['salary']} ₽</code>, мин. ур. <code>{fdata['min_lvl']}</code>, казна <code>{fs['treasury']} ₽</code>"
        )
        rows.append([InlineKeyboardButton(text=f"📝 Подать заявку в {fdata['name']}", callback_data=f"fapp:{fid}")])
    if cur_f in FACTIONS:
        rows.append(
            [
                InlineKeyboardButton(text="📋 Задания фракции", callback_data=f"ftasks:{cur_f}"),
                InlineKeyboardButton(text="🎭 RP-вызов", callback_data=f"frp:{cur_f}"),
            ]
        )
        if int(p.get("rank", 1)) < 10:
            need_pts = int(p.get("rank", 1)) * RANK_UP_POINTS_PER_RANK
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"🎖 Повыситься ({p.get('faction_points', 0)}/{need_pts} оч.)",
                        callback_data=f"fpromo_self:{cur_f}",
                    )
                ]
            )
        rows.append([InlineKeyboardButton(text="🚪 Покинуть фракцию", callback_data="fleave")])
    await safe_answer(message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")


@dp.callback_query(F.data.startswith("fapp:"))
async def cb_faction_apply(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    fdata = FACTIONS.get(fid)
    if not fdata:
        await callback.answer("Фракция не найдена", show_alert=True)
        return
    if p.get("faction", "none") != "none":
        await callback.answer("Вы уже состоите во фракции", show_alert=True)
        return
    if int(p["lvl"]) < int(fdata["min_lvl"]):
        await callback.answer(f"Нужен минимум {fdata['min_lvl']} уровень", show_alert=True)
        return
    app_id = f"{uid}_{fid}"
    faction_apps[app_id] = {
        "id": app_id,
        "user_id": uid,
        "game_id": p["game_id"],
        "name": p["name"],
        "faction": fid,
        "status": "pending",
    }
    save_state()
    await callback.answer(f"Заявка в «{fdata['name']}» отправлена!", show_alert=True)


@dp.callback_query(F.data == "fleave")
async def cb_faction_leave(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    if p.get("faction", "none") == "none":
        await callback.answer("Вы не во фракции", show_alert=True)
        return
    p["faction"] = "none"
    p["rank"] = 1
    p["f_warns"] = 0
    p["leader_of"] = None
    p["active_ftask_id"] = None
    p["active_ftask_ends_at"] = 0.0
    save_state()
    await callback.answer("Вы покинули фракцию", show_alert=True)


@dp.callback_query(F.data.startswith("ftasks:"))
async def cb_ftasks(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return

    now = time.time()
    active_id = p.get("active_ftask_id")
    ends_at = float(p.get("active_ftask_ends_at", 0.0) or 0.0)
    if active_id:
        task_obj = find_faction_task(fid, active_id)
        if task_obj and now < ends_at:
            await callback.answer(
                f"Выполняется задание «{task_obj['title']}». Осталось {format_duration(ends_at - now)}",
                show_alert=True,
            )
            return
        if task_obj and now >= ends_at:
            rew_money = int(task_obj["reward_money"])
            rew_xp = int(task_obj["reward_xp"])
            rew_pts = int(task_obj["points"])
            t_cut = int(task_obj.get("treasury_cut", 0))
            p["money"] += rew_money
            p["xp"] += rew_xp
            p["faction_points"] = int(p.get("faction_points", 0)) + rew_pts
            p["active_ftask_id"] = None
            p["active_ftask_ends_at"] = 0.0
            while p["xp"] >= p["lvl"] * 100:
                p["xp"] -= p["lvl"] * 100
                p["lvl"] += 1
            fs = get_fstate(fid)
            fs["treasury"] = int(fs.get("treasury", 0)) + t_cut
            fs["rating"] = int(fs.get("rating", 0)) + rew_pts
            save_state()
            await callback.answer(
                f"Задание выполнено! +{rew_money} ₽, +{rew_xp} XP, +{rew_pts} очков фракции",
                show_alert=True,
            )
            return

    tasks = get_faction_tasks(fid)
    rows = [
        [
            InlineKeyboardButton(
                text=f"▶️ {t['title'][:28]} ({t['duration_sec'] // 60}м)",
                callback_data=f"ftask_start:{fid}:{t['id']}",
            )
        ]
        for t in tasks
    ]
    if callback.message:
        await callback.message.answer(
            f"📋 <b>Задания фракции «{esc(FACTIONS[fid]['name'])}»</b>\n"
            f"Ваши очки фракции: <b><code>{p.get('faction_points', 0)}</code></b> | Силы: <code>{p['stamina']}/100</code> | Голод: <code>{p['hunger']}/100</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML",
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("ftask_start:"))
async def cb_ftask_start(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    _, fid, tid = callback.data.split(":", 2)
    if p.get("faction") != fid:
        await callback.answer("Вы не в этой фракции", show_alert=True)
        return
    task_obj = find_faction_task(fid, tid)
    if not task_obj:
        await callback.answer("Задание не найдено", show_alert=True)
        return
    st_cost = int(task_obj.get("stamina", 15))
    hg_cost = int(task_obj.get("hunger", 10))
    if int(p["stamina"]) < st_cost:
        await callback.answer(f"Нужно минимум {st_cost} выносливости", show_alert=True)
        return
    if int(p["hunger"]) < hg_cost:
        await callback.answer(f"Нужно минимум {hg_cost} сытости", show_alert=True)
        return

    dur = int(task_obj["duration_sec"])
    p["stamina"] = clamp_stat(int(p["stamina"]) - st_cost)
    p["hunger"] = clamp_stat(int(p["hunger"]) - hg_cost)
    p["active_ftask_id"] = tid
    p["active_ftask_ends_at"] = time.time() + dur
    save_state()
    await callback.answer(f"Задание начато! Длительность: {format_duration(dur)}", show_alert=True)



def get_faction_group_key(fid: str) -> str:
    ftype = str((FACTIONS.get(fid) or {}).get("type") or "gov")
    if ftype == "crime":
        return "crime"
    if ftype == "law":
        return "law"
    return "gov"


def can_manage_faction(actor: dict[str, Any], fid: str) -> bool:
    uid = int(actor.get("tg_id", 0))
    if is_admin(uid, 10):
        return True
    return actor.get("leader_of") == fid or (
        actor.get("faction") == fid and int(actor.get("rank", 1)) >= 11
    )


@dp.message(Command("finfo"))
async def cmd_finfo(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    fid = parts[1].strip().lower() if len(parts) >= 2 else str(p.get("faction") or "none")
    if fid not in FACTIONS:
        await safe_answer(message, "Укажите ключ фракции: <code>/finfo &lt;фракция&gt;</code>", parse_mode="HTML")
        return

    fdata = FACTIONS[fid]
    fs = get_fstate(fid)
    members_cnt = sum(
        1 for u in users.values() if isinstance(u, dict) and u.get("faction") == fid
    )
    leader_names = [
        str(u.get("name"))
        for u in users.values()
        if isinstance(u, dict) and u.get("leader_of") == fid
    ]
    leader_txt = ", ".join(esc(x) for x in leader_names) if leader_names else "<i>Вакантно</i>"

    await safe_answer(
        message,
        f"🏛 <b>Сводка фракции: {esc(fdata['name'])}</b> (<code>{esc(fid)}</code>)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 Лидер: {leader_txt}\n"
        f"👥 Личный состав: <b><code>{members_cnt}</code></b> чел.\n"
        f"🏦 Казна: <b>{esc(format_rub(int(fs.get('treasury', 0))))}</b>\n"
        f"📦 Материалы / снабжение: <b><code>{int(fs.get('materials', 0))}</code></b>\n"
        f"🏅 Рейтинг активности: <b><code>{int(fs.get('rating', 0))}</code></b>\n"
        f"💵 Базовый оклад: <b>{esc(format_rub(int(fdata['salary'])))}</b> | Мин. уровень: <code>{fdata['min_lvl']}</code>",
        parse_mode="HTML",
    )


@dp.message(Command("finvite"))
async def cmd_finvite(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    fid = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 11 else None)
    if not fid or fid not in FACTIONS:
        await safe_answer(message, "⛔ Принимать во фракцию могут лидеры и заместители (11–13 ранги).")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].lstrip("#").isdigit():
        await safe_answer(message, "Формат: <code>/finvite &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1].lstrip("#"))
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    if target.get("faction", "none") != "none":
        await safe_answer(message, "⚠️ Игрок уже состоит в другой фракции.")
        return
    if int(target.get("lvl", 1)) < int(FACTIONS[fid]["min_lvl"]):
        await safe_answer(message, f"⚠️ Для вступления нужен минимум <code>{FACTIONS[fid]['min_lvl']}</code> уровень.", parse_mode="HTML")
        return

    target["faction"] = fid
    target["rank"] = 1
    target["f_warns"] = 0
    target["faction_points"] = 0
    save_state()
    await safe_answer(
        message,
        f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) принят в «{esc(FACTIONS[fid]['name'])}» (1 ранг).",
        parse_mode="HTML",
    )
    await safe_send(bot, int(target["tg_id"]), f"🎉 Вас приняли во фракцию <b>«{esc(FACTIONS[fid]['name'])}»</b>!", parse_mode="HTML")


@dp.message(Command("fkick"))
async def cmd_fkick(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].lstrip("#").isdigit():
        await safe_answer(message, "Формат: <code>/fkick &lt;игровой_ID&gt; [причина]</code>", parse_mode="HTML")
        return
    gid = int(parts[1].lstrip("#"))
    reason = parts[2].strip() if len(parts) == 3 and parts[2].strip() else "Решение руководства фракции"
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    tfac = target.get("faction", "none")
    if tfac not in FACTIONS or not can_manage_faction(actor, tfac):
        await safe_answer(message, "⛔ Недостаточно прав для увольнения этого сотрудника.")
        return
    if int(target.get("tg_id", 0)) == uid:
        await safe_answer(message, "Нельзя уволить самого себя.")
        return

    target["faction"] = "none"
    target["rank"] = 1
    target["f_warns"] = 0
    target["leader_of"] = None
    target["active_ftask_id"] = None
    target["active_ftask_ends_at"] = 0.0
    save_state()
    await safe_answer(
        message,
        f"📤 Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) уволен из фракции «{esc(FACTIONS[tfac]['name'])}».\nПричина: <i>{esc(reason)}</i>",
        parse_mode="HTML",
    )
    await safe_send(bot, int(target["tg_id"]), f"📤 Вы были уволены из фракции <b>«{esc(FACTIONS[tfac]['name'])}»</b>. Причина: {reason}", parse_mode="HTML")


@dp.message(Command("fpromote"))
async def cmd_fpromote(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].lstrip("#").isdigit():
        await safe_answer(message, "Формат: <code>/fpromote &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1].lstrip("#"))
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    tfac = target.get("faction", "none")
    if tfac not in FACTIONS or not can_manage_faction(actor, tfac):
        await safe_answer(message, "⛔ Повышать сотрудников могут лидеры, заместители (11–13) или администрация 10+.")
        return
    cur_rk = int(target.get("rank", 1))
    max_allowed = 13 if is_admin(uid, 11) or actor.get("leader_of") == tfac else 10
    if cur_rk >= max_allowed:
        await safe_answer(message, f"⚠️ Достигнут максимальный доступный ранг (<code>{max_allowed}/13</code>).", parse_mode="HTML")
        return

    target["rank"] = cur_rk + 1
    save_state()
    new_title = get_faction_rank_title(tfac, cur_rk + 1)
    await safe_answer(
        message,
        f"⬆️ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) повышен до звания <b>{esc(new_title)}</b> (<code>{cur_rk + 1}/13</code>)!",
        parse_mode="HTML",
    )
    await safe_send(bot, int(target["tg_id"]), f"⬆️ Вы повышены во фракции до звания <b>{esc(new_title)}</b> (<code>{cur_rk + 1}/13</code>)!", parse_mode="HTML")


@dp.message(Command("fdemote"))
async def cmd_fdemote(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].lstrip("#").isdigit():
        await safe_answer(message, "Формат: <code>/fdemote &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1].lstrip("#"))
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    tfac = target.get("faction", "none")
    if tfac not in FACTIONS or not can_manage_faction(actor, tfac):
        await safe_answer(message, "⛔ Понижать сотрудников могут лидеры, заместители (11–13) или администрация 10+.")
        return
    cur_rk = int(target.get("rank", 1))
    if cur_rk <= 1:
        await safe_answer(message, "⚠️ У игрока уже минимальный 1 ранг.")
        return

    target["rank"] = cur_rk - 1
    save_state()
    new_title = get_faction_rank_title(tfac, cur_rk - 1)
    await safe_answer(
        message,
        f"⬇️ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) понижен до звания <b>{esc(new_title)}</b> (<code>{cur_rk - 1}/13</code>).",
        parse_mode="HTML",
    )
    await safe_send(bot, int(target["tg_id"]), f"⬇️ Ваш ранг во фракции понижен до <b>{esc(new_title)}</b> (<code>{cur_rk - 1}/13</code>).", parse_mode="HTML")


@dp.message(Command("fbonus"))
async def cmd_fbonus(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].lstrip("#").isdigit() or not parts[2].isdigit():
        await safe_answer(message, "Формат: <code>/fbonus &lt;игровой_ID&gt; &lt;сумма&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1].lstrip("#"))
    amount = int(parts[2])
    if not (500 <= amount <= 250_000):
        await safe_answer(message, "Премия должна быть от <code>500 ₽</code> до <code>250 000 ₽</code>.", parse_mode="HTML")
        return
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    tfac = target.get("faction", "none")
    if tfac not in FACTIONS or not can_manage_faction(actor, tfac):
        await safe_answer(message, "⛔ Выдавать премии из казны могут лидеры/заместители фракции или администрация 10+.")
        return

    fs = get_fstate(tfac)
    treasury = int(fs.get("treasury", 0))
    if treasury < amount:
        await safe_answer(message, f"🏦 В казне фракции недостаточно средств (доступно: <b>{esc(format_rub(treasury))}</b>).", parse_mode="HTML")
        return

    now = time.time()
    last_b = float(fs.get("last_bonus", 0.0) or 0.0)
    if not is_admin(uid, 10) and (now - last_b) < FACTION_BONUS_COOLDOWN:
        await safe_answer(
            message,
            f"⏳ Выдавать премии из казны можно раз в {FACTION_BONUS_COOLDOWN // 60} мин. Осталось: <b>{esc(format_duration(FACTION_BONUS_COOLDOWN - (now - last_b)))}</b>.",
            parse_mode="HTML",
        )
        return

    fs["treasury"] = treasury - amount
    fs["last_bonus"] = now
    target["money"] = int(target.get("money", 0)) + amount
    save_state()

    await safe_answer(
        message,
        f"🎖 Выдана премия <b>+{esc(format_rub(amount))}</b> из казны «{esc(FACTIONS[tfac]['name'])}» игроку <b>{esc(target['name'])}</b> (<code>#{gid}</code>)!",
        parse_mode="HTML",
    )
    await safe_send(bot, int(target["tg_id"]), f"🎖 Вам выплачена премия <b>+{esc(format_rub(amount))}</b> из казны фракции «{esc(FACTIONS[tfac]['name'])}»!", parse_mode="HTML")


@dp.callback_query(F.data.startswith("frp:"))
async def cb_frp_menu(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return
    if int(p.get("stamina", 100)) < 15 or int(p.get("hunger", 100)) < 10:
        await callback.answer("Нужно минимум 15 сил и 10 сытости для RP-операции", show_alert=True)
        return

    grp = get_faction_group_key(fid)
    pool = FACTION_RP_SCENARIOS.get(grp) or FACTION_RP_SCENARIOS["gov"]
    sc = random.choice(pool)
    opt_a_txt = sc["opt_a"][0]
    opt_b_txt = sc["opt_b"][0]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=opt_a_txt[:42], callback_data=f"frp_do:{fid}:{sc['id']}:a")],
            [InlineKeyboardButton(text=opt_b_txt[:42], callback_data=f"frp_do:{fid}:{sc['id']}:b")],
        ]
    )
    if callback.message:
        await safe_answer(
            callback.message,
            f"🎭 <b>RP-ситуация · {esc(FACTIONS[fid]['name'])}</b>\n"
            f"<b>{esc(sc['title'])}</b>\n\n"
            f"<i>{esc(sc['desc'])}</i>\n\n"
            f"Выберите действие:",
            reply_markup=kb,
            parse_mode="HTML",
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("frp_do:"))
async def cb_frp_do(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    _, fid, sc_id, choice = callback.data.split(":", 3)
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не состоите в этой фракции", show_alert=True)
        return
    if int(p.get("stamina", 100)) < 15 or int(p.get("hunger", 100)) < 10:
        await callback.answer("Недостаточно сил или сытости", show_alert=True)
        return

    grp = get_faction_group_key(fid)
    pool = FACTION_RP_SCENARIOS.get(grp) or FACTION_RP_SCENARIOS["gov"]
    sc = next((x for x in pool if x["id"] == sc_id), pool[0])
    _, base_money, base_xp, base_pts = sc["opt_a"] if choice == "a" else sc["opt_b"]

    mult = random.choice([0.9, 1.0, 1.15, 1.3])
    rew_money = int(base_money * mult)
    rew_xp = int(base_xp * mult)
    rew_pts = max(5, int(base_pts * mult))
    t_cut = int(rew_money * 0.25)

    p["money"] += rew_money
    p["xp"] += rew_xp
    p["faction_points"] = int(p.get("faction_points", 0)) + rew_pts
    p["stamina"] = clamp_stat(int(p.get("stamina", 100)) - 15)
    p["hunger"] = clamp_stat(int(p.get("hunger", 100)) - 10)
    while p["xp"] >= p["lvl"] * 100:
        p["xp"] -= p["lvl"] * 100
        p["lvl"] += 1

    fs = get_fstate(fid)
    fs["treasury"] = int(fs.get("treasury", 0)) + t_cut
    fs["rating"] = int(fs.get("rating", 0)) + rew_pts
    save_state()

    verdict = "Отличный отыгрыш! Премия повышена." if mult > 1.0 else "RP-сценарий успешно отыгран."
    await callback.answer(f"+{rew_money} ₽ | +{rew_pts} очков фракции", show_alert=True)
    if callback.message:
        await safe_answer(
            callback.message,
            f"✅ <b>{verdict}</b>\n"
            f"Фракция: <b>{esc(FACTIONS[fid]['name'])}</b>\n"
            f"Награда: <b>+{rew_money} ₽</b> · <b>+{rew_xp} XP</b> · <b>+{rew_pts} очков</b> (в казну: +{t_cut} ₽).",
            parse_mode="HTML",
        )


@dp.callback_query(F.data.startswith("fpromo_self:"))
async def cb_fpromo_self(callback: CallbackQuery):
    uid = callback.from_user.id
    p = get_player(uid, callback.from_user.full_name)
    fid = callback.data.split(":", 1)[1]
    if p.get("faction") != fid or fid not in FACTIONS:
        await callback.answer("Вы не во фракции", show_alert=True)
        return
    cur_rk = int(p.get("rank", 1))
    if cur_rk >= 10:
        await callback.answer("С 10 ранга повышение происходит через руководство фракции или администрацию", show_alert=True)
        return
    pts = int(p.get("faction_points", 0))
    need_pts = cur_rk * RANK_UP_POINTS_PER_RANK
    if pts < need_pts:
        await callback.answer(f"Нужно {need_pts} очков службы (у вас {pts})", show_alert=True)
        return

    p["faction_points"] = pts - need_pts
    p["rank"] = cur_rk + 1
    save_state()
    new_title = get_faction_rank_title(fid, cur_rk + 1)
    await callback.answer(f"Повышение до {new_title} ({cur_rk + 1}/13)!", show_alert=True)
    if callback.message:
        await safe_answer(
            callback.message,
            f"🎖 Вы повышены по выслуге и очкам службы до звания <b>{esc(new_title)}</b> (<code>{cur_rk + 1}/13</code>)!",
            parse_mode="HTML",
        )

@dp.message(Command("fapps"))
async def cmd_fapps(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("leader_of") or (p.get("faction") if int(p.get("rank", 1)) >= 11 else None)
    if not fid or fid not in FACTIONS:
        await safe_answer(message, "⛔ Просматривать заявки во фракцию могут лидеры и заместители (11–13 ранги).")
        return
    pending = [a for a in faction_apps.values() if a.get("faction") == fid and a.get("status") == "pending"]
    if not pending:
        await safe_answer(message, f"В фракцию <b>{esc(FACTIONS[fid]['name'])}</b> пока нет открытых заявок.", parse_mode="HTML")
        return
    lines = [f"📄 <b>Заявки в «{esc(FACTIONS[fid]['name'])}»</b>:\n"]
    for a in pending[:20]:
        lines.append(f"• <b>{esc(a['name'])}</b> (игровой ID: <code>#{a['game_id']}</code>) — принять: <code>/faccept {a['game_id']}</code>")
    await safe_answer(message, "\n".join(lines), parse_mode="HTML")


@dp.message(Command("faccept"))
async def cmd_faccept(message: Message, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("leader_of") or (p.get("faction") if int(p.get("rank", 1)) >= 11 else None)
    if not fid or fid not in FACTIONS:
        await safe_answer(message, "⛔ Принимать во фракцию могут лидеры и заместители (11–13 ранги).")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/faccept &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1])
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "accepted"
    target["faction"] = fid
    target["rank"] = 1
    target["f_warns"] = 0
    save_state()
    await safe_answer(message, f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) принят в «{esc(FACTIONS[fid]['name'])}».", parse_mode="HTML")
    await safe_send(bot, int(target["tg_id"]), f"🎉 Вы приняты во фракцию <b>«{esc(FACTIONS[fid]['name'])}»</b>!", parse_mode="HTML")


@dp.message(Command("fdecline"))
async def cmd_fdecline(message: Message, bot: Bot):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("leader_of") or (p.get("faction") if int(p.get("rank", 1)) >= 11 else None)
    if not fid or fid not in FACTIONS:
        await safe_answer(message, "⛔ Отклонять заявки могут лидеры и заместители (11–13 ранги).")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/fdecline &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1])
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    app_id = f"{target['tg_id']}_{fid}"
    if app_id in faction_apps:
        faction_apps[app_id]["status"] = "declined"
    save_state()
    await safe_answer(message, f"❌ Заявка игрока <b>{esc(target['name'])}</b> (<code>#{gid}</code>) отклонена.", parse_mode="HTML")
    await safe_send(bot, int(target["tg_id"]), f"❌ Ваша заявка во фракцию <b>«{esc(FACTIONS[fid]['name'])}»</b> отклонена.", parse_mode="HTML")


@dp.message(Command("fdeposit"))
async def cmd_fdeposit(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    fid = p.get("faction", "none")
    if fid not in FACTIONS:
        await safe_answer(message, "Вы не состоите во фракции.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/fdeposit &lt;сумма&gt;</code>", parse_mode="HTML")
        return
    amount = int(parts[1])
    if amount < 100 or amount > 5_000_000:
        await safe_answer(message, "Сумма пополнения казны — от 100 до 5 000 000 ₽.")
        return
    if p["money"] < amount:
        await safe_answer(message, "Недостаточно наличных.")
        return
    p["money"] -= amount
    fs = get_fstate(fid)
    fs["treasury"] = int(fs.get("treasury", 0)) + amount
    save_state()
    await safe_answer(message, f"🏦 Казна фракции пополнена на <b>+{amount} ₽</b>. Текущая казна: <b>{fs['treasury']} ₽</b>.", parse_mode="HTML")


@dp.message(Command("fwarn"))
async def cmd_fwarn(message: Message, bot: Bot):
    uid = message.from_user.id
    actor = get_player(uid, message.from_user.full_name)
    actor_fac = actor.get("leader_of") or (actor.get("faction") if int(actor.get("rank", 1)) >= 11 else None)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/fwarn &lt;игровой_ID&gt; [причина]</code>", parse_mode="HTML")
        return

    target_gid = int(parts[1])
    reason = parts[2].strip() if len(parts) == 3 and parts[2].strip() else "Нарушение устава фракции"
    target = find_player_by_game_id(target_gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{target_gid}</code> не найден.", parse_mode="HTML")
        return

    tfac = target.get("faction", "none")
    if tfac not in FACTIONS:
        await safe_answer(message, "Игрок не состоит ни в одной фракции.")
        return

    if not is_admin(uid, 7):
        if not actor_fac or actor_fac != tfac:
            await safe_answer(message, "⛔ Выдавать выговоры можно только сотрудникам своей фракции (лидерам / 11+ рангам или админам 7+).")
            return
        if int(actor.get("tg_id", 0)) == int(target.get("tg_id", 0)):
            await safe_answer(message, "Нельзя выдать выговор самому себе.")
            return

    warns = int(target.get("f_warns", 0)) + 1
    fac_title = FACTIONS[tfac]["name"]
    t_uid = int(target["tg_id"])

    if warns >= 3:
        target["faction"] = "none"
        target["rank"] = 1
        target["f_warns"] = 0
        target["leader_of"] = None
        target["active_ftask_id"] = None
        target["active_ftask_ends_at"] = 0.0
        save_state()
        await safe_answer(
            message,
            f"🚫 Игрок <b>{esc(target['name'])}</b> (<code>#{target_gid}</code>) получил <b>3/3 выговор</b> и уволен из фракции «{esc(fac_title)}»!\nПричина: <i>{esc(reason)}</i>",
            parse_mode="HTML",
        )
        await safe_send(bot, t_uid, f"🚫 Вы уволены из фракции <b>«{esc(fac_title)}»</b> за 3/3 выговоров. Причина: {esc(reason)}", parse_mode="HTML")
    else:
        target["f_warns"] = warns
        save_state()
        await safe_answer(
            message,
            f"⚠️ Игроку <b>{esc(target['name'])}</b> (<code>#{target_gid}</code>) выдан выговор фракции <b><code>{warns}/3</code></b>.\nПричина: <i>{esc(reason)}</i>",
            parse_mode="HTML",
        )
        await safe_send(bot, t_uid, f"⚠️ Вы получили выговор во фракции <b>«{esc(fac_title)}»</b> (<code>{warns}/3</code>). Причина: {esc(reason)}", parse_mode="HTML")


@dp.message(Command("r"))
async def cmd_faction_radio(message: Message, bot: Bot):
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
    rk_title = get_faction_rank_title(fid, int(p["rank"]))
    msg_txt = f"📡 <b>[R] [{esc(FACTIONS[fid]['name'])}] {esc(rk_title)} {esc(p['name'])}:</b> {esc(parts[1].strip())}"
    sent = 0
    for k, u in users.items():
        if isinstance(u, dict) and u.get("faction") == fid:
            try:
                await safe_send(bot, int(k), msg_txt, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
    await safe_answer(message, f"✅ Сообщение отправлено в рацию фракции (<code>{sent}</code> сослуживцам).", parse_mode="HTML")


@dp.message(Command("setleader"))
async def cmd_setleader(message: Message, bot: Bot):
    uid = message.from_user.id
    if not is_admin(uid, 11):
        await safe_answer(message, "⛔ Назначать лидеров фракций можно с 11 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit():
        keys_str = ", ".join(f"<code>{esc(k)}</code>" for k in FACTIONS)
        await safe_answer(message, f"Формат: <code>/setleader &lt;игровой_ID&gt; &lt;фракция|none&gt;</code>\nФракции: {keys_str}", parse_mode="HTML")
        return
    gid = int(parts[1])
    fid = parts[2].strip().lower()
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    t_uid = int(target["tg_id"])
    if fid == "none":
        target["leader_of"] = None
        target["faction"] = "none"
        target["rank"] = 1
        save_state()
        await safe_answer(message, f"✅ Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) снят с поста лидера.", parse_mode="HTML")
        return
    if fid not in FACTIONS:
        await safe_answer(message, "Неизвестный ключ фракции.")
        return
    target["faction"] = fid
    target["rank"] = 13
    target["leader_of"] = fid
    target["f_warns"] = 0
    save_state()
    await safe_answer(message, f"👑 Игрок <b>{esc(target['name'])}</b> (<code>#{gid}</code>) назначен лидером «{esc(FACTIONS[fid]['name'])}» (13 ранг).", parse_mode="HTML")
    await safe_send(bot, t_uid, f"👑 Вы назначены лидером фракции <b>«{esc(FACTIONS[fid]['name'])}»</b>!", parse_mode="HTML")


@dp.message(Command("bank"))
async def cmd_bank(message: Message):
    uid = message.from_user.id
    p = get_player(uid, message.from_user.full_name)
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1].lower() not in {"put", "take"} or not parts[2].isdigit():
        await safe_answer(
            message,
            f"🏦 <b>Банк:</b> наличные <b>{p['money']} ₽</b> | счёт <b>{p['bank']} ₽</b>\n"
            f"Команды: <code>/bank put &lt;сумма&gt;</code> или <code>/bank take &lt;сумма&gt;</code>",
            parse_mode="HTML",
        )
        return
    action = parts[1].lower()
    amount = int(parts[2])
    if amount <= 0:
        await safe_answer(message, "Сумма должна быть больше нуля.")
        return
    if action == "put":
        if p["money"] < amount:
            await safe_answer(message, "Недостаточно наличных.")
            return
        p["money"] -= amount
        p["bank"] += amount
        save_state()
        await safe_answer(message, f"🏦 Внесено <b>+{amount} ₽</b>. Наличные: <b>{p['money']} ₽</b> | Банк: <b>{p['bank']} ₽</b>.", parse_mode="HTML")
    else:
        if p["bank"] < amount:
            await safe_answer(message, "Недостаточно средств на банковском счёте.")
            return
        p["bank"] -= amount
        p["money"] += amount
        save_state()
        await safe_answer(message, f"🏦 Снято <b>{amount} ₽</b>. Наличные: <b>{p['money']} ₽</b> | Банк: <b>{p['bank']} ₽</b>.", parse_mode="HTML")


@dp.message(Command("resetplayer"))
async def cmd_resetplayer(message: Message):
    uid = message.from_user.id
    if not is_admin(uid, 14):
        await safe_answer(message, "⛔ Обнулять аккаунты игроков можно с 14 ранга администратора.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await safe_answer(message, "Формат: <code>/resetplayer &lt;игровой_ID&gt;</code>", parse_mode="HTML")
        return
    gid = int(parts[1])
    target = find_player_by_game_id(gid)
    if not target:
        await safe_answer(message, f"Игрок <code>#{gid}</code> не найден.", parse_mode="HTML")
        return
    t_uid = int(target["tg_id"])
    if is_creator(t_uid):
        await safe_answer(message, "Нельзя обнулить создателя.")
        return
    fresh = normalize_player({"name": target["name"], "registered": True, "game_id": gid}, t_uid)
    users[str(t_uid)] = fresh
    save_state()
    await safe_answer(message, f"♻️ Аккаунт игрока <b>{esc(fresh['name'])}</b> (<code>#{gid}</code>) обнулён.", parse_mode="HTML")


@dp.message(Command("wipeall"))
async def cmd_wipeall(message: Message):
    uid = message.from_user.id
    if not is_creator(uid):
        await safe_answer(message, "⛔ Полный вайп данных доступен только создателю проекта.")
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or parts[1] != "CONFIRM":
        await safe_answer(message, "⚠️ Опасная команда! Для полного вайпа введите: <code>/wipeall CONFIRM</code>", parse_mode="HTML")
        return
    users.clear()
    faction_apps.clear()
    families.clear()
    promocodes.clear()
    support_tickets.clear()
    for b in businesses.values():
        b["owner_uid"] = None
        b["owner_name"] = None
        b["cash"] = 0
        b["last_collect"] = 0.0
    for fid, fdef in DEFAULT_FACTION_STATE.items():
        faction_state[fid] = dict(fdef)
    save_state()
    await safe_answer(message, "🧹 Все игровые данные обнулены и сохранены.", parse_mode="HTML")


async def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError("Укажите BOT_TOKEN в переменных окружения или в файле pixel_3.py")
    load_state()
    save_state()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())