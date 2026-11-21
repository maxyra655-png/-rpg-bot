import asyncio
import json
import logging
import os
import random
import boss
import time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = 5516435343  # Твой числовой Telegram ID (без кавычек)

WORK_COOLDOWN = 20
LEADER_BONUS_COOLDOWN = 30
MEDIA_REWARD_COOLDOWN = 300
MEDIA_REWARD_COINS = 100
MEDIA_REWARD_XP = 25

DAILY_COOLDOWN = 86400
DAILY_STREAK_WINDOW = 172800
QUEST_TARGET_ACTIONS = 5
QUEST_REWARD_COINS = 120
QUEST_REWARD_XP = 30

MAX_HP = 100
START_GAME_ID = 1001
DATA_FILE = "data.json"

SHOP_ITEMS = {
    "medkit": {"name": "🩺 Аптечка (+35 HP)", "price": 40, "hp": 35},
    "amulet": {"name": "🛡 Амулет удачи (+5 к добыче)", "price": 120, "bonus": 5},
    "blade": {"name": "⚔️ Клинок рейда (+12 к добыче)", "price": 260, "bonus": 12},
}

FACTIONS = {
    "guards": {
        "name": "⚔️ Стражи",
        "desc": "+4 к добыче в работе/рейде",
        "work_bonus": 4,
        "dice_bonus": 0,
        "hp_bonus": 0,
    },
    "seekers": {
        "name": "🍀 Искатели",
        "desc": "+6 к выигрышу в риск-броске",
        "work_bonus": 0,
        "dice_bonus": 6,
        "hp_bonus": 0,
    },
    "bastion": {
        "name": "🛡 Бастион",
        "desc": "+15 к макс. HP",
        "work_bonus": 0,
        "dice_bonus": 0,
        "hp_bonus": 15,
    },
}

bot = Bot(token=TOKEN)
dp = Dispatcher()
dp.include_router(boss.router)

users: dict[int, dict] = {}             # tg_id -> данные игрока
game_to_tg: dict[int, int] = {}           # game_id -> tg_id
next_game_id: int = START_GAME_ID
admins: set[int] = set()                  # набор игровых ID админов
faction_leaders: dict[str, int] = {}      # faction_key -> game_id лидера
media_creators: set[int] = set()          # набор tg_id медиа-создателей
promo_codes: dict[str, dict] = {}         # promo_code -> данные промокода


def default_user_profile(tg_id: int, gid: int, name: str = "Игрок") -> dict:
    return {
        "tg_id": tg_id,
        "game_id": gid,
        "name": name or "Игрок",
        "coins": 0,
        "hp": MAX_HP,
        "xp": 0,
        "level": 1,
        "last_work": 0.0,
        "last_leader_bonus": 0.0,
        "last_media_reward": 0.0,
        "last_daily": 0.0,
        "daily_streak": 0,
        "quests_done": 0,
        "quest_claimed": False,
        "used_promos": [],
        "items": [],
        "power_bonus": 0,
        "faction": None,
    }


def get_user_by_game_id(game_id: int) -> dict | None:
    tg_id = game_to_tg.get(game_id)
    if tg_id is None:
        return None
    return users.get(tg_id)


def load_data() -> None:
    global users, game_to_tg, next_game_id, admins, faction_leaders, media_creators, promo_codes

    users = {}
    game_to_tg = {}
    admins = set()
    faction_leaders = {}
    media_creators = set()
    promo_codes = {}
    next_game_id = START_GAME_ID

    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logging.error(f"Не удалось прочитать {DATA_FILE}: {e}")
        return

    if not isinstance(raw, dict):
        return

    raw_users = raw.get("users", {})
    if isinstance(raw_users, dict):
        for k, v in raw_users.items():
            if not isinstance(v, dict):
                continue
            try:
                tg_id = int(v.get("tg_id", k))
            except (TypeError, ValueError):
                continue

            gid_raw = v.get("game_id")
            try:
                gid = int(gid_raw)
            except (TypeError, ValueError):
                while next_game_id in game_to_tg:
                    next_game_id += 1
                gid = next_game_id
                next_game_id += 1

            profile = default_user_profile(tg_id, gid, str(v.get("name") or "Игрок"))
            profile["coins"] = int(v.get("coins", 0))
            profile["hp"] = int(v.get("hp", MAX_HP))
            profile["xp"] = int(v.get("xp", 0))
            profile["level"] = int(v.get("level", 1))
            profile["last_work"] = float(v.get("last_work", 0.0))
            profile["last_leader_bonus"] = float(v.get("last_leader_bonus", 0.0))
            profile["last_media_reward"] = float(v.get("last_media_reward", 0.0))
            profile["last_daily"] = float(v.get("last_daily", 0.0))
            profile["daily_streak"] = int(v.get("daily_streak", 0))
            profile["quests_done"] = int(v.get("quests_done", 0))
            profile["quest_claimed"] = bool(v.get("quest_claimed", False))
            raw_used = v.get("used_promos")
            profile["used_promos"] = [str(x).upper() for x in raw_used] if isinstance(raw_used, list) else []
            profile["items"] = list(v.get("items") or [])
            profile["power_bonus"] = int(v.get("power_bonus", 0))
            fac = v.get("faction")
            profile["faction"] = fac if fac in FACTIONS else None

            for extra_key, extra_val in v.items():
                if extra_key not in profile:
                    profile[extra_key] = extra_val

            users[tg_id] = profile
            game_to_tg[gid] = tg_id

    raw_admins = raw.get("admins", [])
    if isinstance(raw_admins, list):
        for adm_id in raw_admins:
            try:
                admins.add(int(adm_id))
            except (TypeError, ValueError):
                continue

    raw_leaders = raw.get("faction_leaders", {})
    if isinstance(raw_leaders, dict):
        for f_key, leader_gid in raw_leaders.items():
            if f_key not in FACTIONS:
                continue
            try:
                lgid = int(leader_gid)
            except (TypeError, ValueError):
                continue
            leader_user = get_user_by_game_id(lgid)
            if leader_user and leader_user.get("faction") == f_key:
                faction_leaders[f_key] = lgid

    raw_media = raw.get("media_creators", [])
    if isinstance(raw_media, list):
        for mid in raw_media:
            try:
                media_creators.add(int(mid))
            except (TypeError, ValueError):
                continue

    raw_promos = raw.get("promo_codes", {})
    if isinstance(raw_promos, dict):
        for code, info in raw_promos.items():
            if isinstance(info, dict):
                promo_codes[str(code).upper()] = {
                    "coins": int(info.get("coins", 0)),
                    "uses": int(info.get("uses", 0)),
                    "max_uses": int(info.get("max_uses", 1)),
                    "creator_gid": int(info.get("creator_gid", 0)),
                }

    max_existing_id = max(game_to_tg.keys(), default=START_GAME_ID - 1)
    saved_next_id = raw.get("next_game_id", START_GAME_ID)
    try:
        saved_next_id = int(saved_next_id)
    except (TypeError, ValueError):
        saved_next_id = START_GAME_ID

    next_game_id = max(START_GAME_ID, saved_next_id, max_existing_id + 1)


def save_data() -> None:
    payload = {
        "next_game_id": next_game_id,
        "admins": sorted(admins),
        "faction_leaders": faction_leaders,
        "media_creators": sorted(media_creators),
        "promo_codes": promo_codes,
        "users": {str(tg_id): profile for tg_id, profile in users.items()},
    }
    tmp_file = f"{DATA_FILE}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, DATA_FILE)


class GameStates(StatesGroup):
    waiting_give_coins = State()
    waiting_give_hp = State()
    waiting_set_game_id = State()
    waiting_add_admin = State()
    waiting_remove_admin = State()
    waiting_set_leader = State()
    waiting_leader_bonus = State()
    waiting_leader_kick = State()
    waiting_broadcast = State()
    waiting_set_level = State()
    waiting_give_item = State()
    waiting_set_faction = State()
    waiting_reset_confirm = State()
    waiting_toggle_media = State()
    waiting_create_promo = State()
    waiting_media_reward_gid = State()
    waiting_activate_promo = State()
    waiting_transfer_input = State()
    waiting_duel_input = State()
    waiting_slots_bet = State()
    waiting_lookup_gid = State()


def is_owner(tg_id: int) -> bool:
    return tg_id == OWNER_ID


def is_admin(tg_id: int) -> bool:
    if is_owner(tg_id):
        return True
    user = users.get(tg_id)
    return bool(user and user["game_id"] in admins)


def is_media(tg_id: int) -> bool:
    return tg_id in media_creators or is_admin(tg_id)


def get_user(tg_id: int, name: str = "Игрок") -> dict:
    global next_game_id
    changed = False
    if tg_id not in users:
        while next_game_id in game_to_tg:
            next_game_id += 1
        gid = next_game_id
        next_game_id += 1

        users[tg_id] = default_user_profile(tg_id, gid, name)
        game_to_tg[gid] = tg_id
        changed = True
    else:
        u = users[tg_id]
        if name and u.get("name") != name:
            u["name"] = name
            changed = True
        if "last_media_reward" not in u:
            u["last_media_reward"] = 0.0
            changed = True
        if "last_daily" not in u:
            u["last_daily"] = 0.0
            changed = True
        if "daily_streak" not in u:
            u["daily_streak"] = 0
            changed = True
        if "quests_done" not in u:
            u["quests_done"] = 0
            changed = True
        if "quest_claimed" not in u:
            u["quest_claimed"] = False
            changed = True
        if not isinstance(u.get("used_promos"), list):
            u["used_promos"] = []
            changed = True

    if changed:
        save_data()
    return users[tg_id]


def get_max_hp(user: dict) -> int:
    fac_key = user.get("faction")
    fac = FACTIONS.get(fac_key) if fac_key else None
    hp_bonus = fac.get("hp_bonus", 0) if fac else 0
    return MAX_HP + hp_bonus


def is_faction_leader(user: dict) -> bool:
    fac_key = user.get("faction")
    if not fac_key or fac_key not in FACTIONS:
        return False
    return faction_leaders.get(fac_key) == user.get("game_id")


def get_faction_label(user: dict) -> str:
    fac_key = user.get("faction")
    if fac_key and fac_key in FACTIONS:
        base = FACTIONS[fac_key]["name"]
        if is_faction_leader(user):
            return f"{base} (👑 Лидер)"
        return base
    return "Без фракции"


def add_xp(user: dict, amount: int) -> bool:
    user["xp"] += amount
    leveled_up = False
    max_hp = get_max_hp(user)
    while user["xp"] >= user["level"] * 50:
        user["xp"] -= user["level"] * 50
        user["level"] += 1
        user["hp"] = max_hp
        leveled_up = True
    return leveled_up


load_data()


def format_profile(user: dict, note: str = "") -> str:
    items = user.get("items") or []
    items_text = ", ".join(items) if items else "пусто"
    level = user.get("level", 1)
    xp = user.get("xp", 0)
    needed_xp = level * 50
    max_hp = get_max_hp(user)
    streak = int(user.get("daily_streak", 0))

    if is_owner(user["tg_id"]):
        role_badge = "👑 Владелец"
    elif user["game_id"] in admins:
        role_badge = "🛡 Админ"
    elif user["tg_id"] in media_creators:
        role_badge = "🎬 Медиа"
    elif is_faction_leader(user):
        role_badge = "⚜️ Лидер фракции"
    else:
        role_badge = "🎮 Игрок"

    base_text = (
        f"🎮 **Профиль: {user['name']}** ({role_badge})\n"
        f"🆔 Игровой ID: **`{user['game_id']}`**\n"
        f"🏴 Фракция: **{get_faction_label(user)}**\n\n"
        f"🏅 Уровень: **{level}** (`{xp}/{needed_xp} XP`)\n"
        f"💰 Монеты: **{user.get('coins', 0)}**\n"
        f"❤️ HP: **{user.get('hp', max_hp)}/{max_hp}**\n"
        f"⚡ Бонус силы: **+{user.get('power_bonus', 0)}**\n"
        f"🔥 Серия входов: **{streak}** дн.\n"
        f"🎒 Рюкзак: *{items_text}*"
    )
    if note:
        base_text += f"\n\n{note}"
    return base_text


def main_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="⛏ Работа / Рейд", callback_data="act_work"),
            InlineKeyboardButton(text="🎲 Риск-бросок", callback_data="act_dice"),
        ],
        [
            InlineKeyboardButton(text="🛒 Магазин", callback_data="menu_shop"),
            InlineKeyboardButton(text="🏴 Фракция", callback_data="menu_faction"),
        ],
        [
            InlineKeyboardButton(text="📅 Ежедневка", callback_data="act_daily"),
            InlineKeyboardButton(text="🎮 Игровые фичи", callback_data="menu_extra"),
        ],
        [
            InlineKeyboardButton(text="🎟 Промокод", callback_data="act_promo"),
            InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_profile"),
        ],
    ]
    if is_media(tg_id):
        rows.append([InlineKeyboardButton(text="🎬 Медиа-панель", callback_data="media_panel")])
    if is_admin(tg_id):
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def extra_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💸 Перевод по ID", callback_data="act_transfer"),
                InlineKeyboardButton(text="⚔️ Дуэль по ID", callback_data="act_duel"),
            ],
            [
                InlineKeyboardButton(text="🎰 Слоты", callback_data="act_slots"),
                InlineKeyboardButton(text="📜 Квест дня", callback_data="menu_quest"),
            ],
            [
                InlineKeyboardButton(text="🔍 Найти по ID", callback_data="act_lookup"),
                InlineKeyboardButton(text="⬅️ В профиль", callback_data="back_main"),
            ],
        ]
    )


def shop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🩺 Аптечка (+35 HP) — 40 монет", callback_data="buy_medkit")],
            [InlineKeyboardButton(text="🛡 Амулет удачи (+5) — 120 монет", callback_data="buy_amulet")],
            [InlineKeyboardButton(text="⚔️ Клинок рейда (+12) — 260 монет", callback_data="buy_blade")],
            [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_main")],
        ]
    )


def faction_keyboard(user: dict) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{f['name']} ({f['desc']})",
                callback_data=f"set_faction_{key}",
            )
        ]
        for key, f in FACTIONS.items()
    ]
    if is_faction_leader(user):
        rows.append([
            InlineKeyboardButton(text="🎁 Премия участнику (+25)", callback_data="ldr_bonus"),
            InlineKeyboardButton(text="👢 Исключить игрока", callback_data="ldr_kick"),
        ])
    if user.get("faction"):
        rows.append([InlineKeyboardButton(text="🚪 Покинуть фракцию", callback_data="leave_faction")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_main")]]
    )


def admin_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📢 Объявление всем", callback_data="adm_broadcast"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton(text="💰 Выдать монеты", callback_data="adm_give_coins"),
            InlineKeyboardButton(text="❤️ Выдать HP", callback_data="adm_give_hp"),
        ],
        [
            InlineKeyboardButton(text="⭐ Задать уровень", callback_data="adm_set_level"),
            InlineKeyboardButton(text="🎒 Выдать предмет", callback_data="adm_give_item"),
        ],
        [
            InlineKeyboardButton(text="🏴 Фракция игроку", callback_data="adm_set_faction"),
            InlineKeyboardButton(text="👑 Лидер фракции", callback_data="adm_set_leader"),
        ],
        [
            InlineKeyboardButton(text="🆔 Сменить ID", callback_data="adm_set_id"),
            InlineKeyboardButton(text="🔄 Сброс игрока", callback_data="adm_reset_user"),
        ],
        [
            InlineKeyboardButton(text="🎬 Медиа-роли", callback_data="adm_media_role"),
        ],
    ]
    if is_owner(tg_id):
        rows.append([
            InlineKeyboardButton(text="➕ Дать админку", callback_data="adm_add_admin"),
            InlineKeyboardButton(text="➖ Снять админку", callback_data="adm_del_admin"),
        ])
    rows.append([InlineKeyboardButton(text="❌ Отмена ввода", callback_data="adm_cancel")])
    rows.append([InlineKeyboardButton(text="⬅️ В профиль", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def media_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Выдать медиа-награду", callback_data="med_reward")],
            [InlineKeyboardButton(text="🎟 Создать промокод", callback_data="med_create_promo")],
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="med_stats")],
            [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_main")],
        ]
    )


async def safe_edit_or_send(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    await message.answer(
        format_profile(user, "👋 Добро пожаловать! Выбирай фракцию и прокачивай героя."),
        reply_markup=main_keyboard(uid),
        parse_mode="Markdown",
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.answer("⛔ Нет доступа к админ-панели.")
        return
    await state.clear()
    await message.answer(
        "🛠 **Админ-панель** (все действия по игровому ID)\nВыбери действие:",
        reply_markup=admin_keyboard(uid),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data.in_({"back_main", "refresh_profile"}))
async def on_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    await safe_edit_or_send(callback, format_profile(user), main_keyboard(uid))
    await callback.answer()


@dp.callback_query(F.data == "act_work")
async def on_work(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    now = time.time()
    rem = int(WORK_COOLDOWN - (now - user.get("last_work", 0.0)))
    if rem > 0:
        await callback.answer(f"⏳ Подожди ещё {rem} сек.", show_alert=True)
        return

    fac = FACTIONS.get(user.get("faction") or "")
    fac_work_bonus = fac["work_bonus"] if fac else 0
    leader_bonus = 3 if is_faction_leader(user) else 0

    user["last_work"] = now
    earned = random.randint(15, 30) + user.get("power_bonus", 0) + fac_work_bonus + leader_bonus
    hp_loss = random.randint(3, 12)
    max_hp = get_max_hp(user)
    user["coins"] = user.get("coins", 0) + earned
    user["hp"] = max(1, min(max_hp, user.get("hp", max_hp) - hp_loss))
    user["quests_done"] = int(user.get("quests_done", 0)) + 1
    leveled = add_xp(user, 15)
    save_data()

    note = f"⛏ Вылазка удалась! **+{earned}** монет, **-{hp_loss}** HP, **+15 XP**."
    if leveled:
        note += f"\n🎉 **Новый уровень: {user['level']}!** HP восстановлено до {max_hp}."

    await safe_edit_or_send(callback, format_profile(user, note), main_keyboard(uid))
    await callback.answer(f"+{earned} монет")


@dp.callback_query(F.data == "act_dice")
async def on_dice(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    bet = 20
    if user.get("coins", 0) < bet:
        await callback.answer("Нужно минимум 20 монет для риск-броска!", show_alert=True)
        return

    fac = FACTIONS.get(user.get("faction") or "")
    fac_dice_bonus = fac["dice_bonus"] if fac else 0

    roll_val = random.randint(1, 6)
    if roll_val >= 4:
        win = 35 + user.get("power_bonus", 0) + fac_dice_bonus
        user["coins"] += win - bet
        leveled = add_xp(user, 10)
        note = f"🎲 Выпало **{roll_val}**! Победа: **+{win - bet}** монет и **+10 XP**."
        if leveled:
            note += f"\n🎉 **Новый уровень: {user['level']}!**"
    else:
        user["coins"] -= bet
        note = f"🎲 Выпало **{roll_val}**. Не повезло: потеряно **{bet}** монет."

    user["quests_done"] = int(user.get("quests_done", 0)) + 1
    save_data()
    await safe_edit_or_send(callback, format_profile(user, note), main_keyboard(uid))
    await callback.answer(f"Выпало {roll_val}")


@dp.callback_query(F.data == "menu_shop")
async def on_menu_shop(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    max_hp = get_max_hp(user)
    text = (
        f"🛒 **Магазин**\n"
        f"💰 Твой баланс: **{user.get('coins', 0)}** монет | ❤️ HP: **{user.get('hp', max_hp)}/{max_hp}**\n\n"
        f"Выбери предмет для покупки:"
    )
    await safe_edit_or_send(callback, text, shop_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def on_buy(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    item_key = callback.data.removeprefix("buy_")
    item = SHOP_ITEMS.get(item_key)
    if not item:
        await callback.answer("Предмет не найден", show_alert=True)
        return

    if user.get("coins", 0) < item["price"]:
        await callback.answer(f"Не хватает монет! Нужно {item['price']}.", show_alert=True)
        return

    user["coins"] -= item["price"]
    msg_extra = ""
    if "hp" in item:
        max_hp = get_max_hp(user)
        old_hp = user.get("hp", max_hp)
        user["hp"] = min(max_hp, old_hp + item["hp"])
        msg_extra = f"HP восстановлено: **{old_hp} → {user['hp']}**."
    elif "bonus" in item:
        user["power_bonus"] = user.get("power_bonus", 0) + item["bonus"]
        items = user.setdefault("items", [])
        items.append(item["name"])
        msg_extra = f"Бонус силы теперь **+{user['power_bonus']}**."

    save_data()
    text = (
        f"✅ Куплено: **{item['name']}**!\n"
        f"{msg_extra}\n"
        f"💰 Остаток монет: **{user['coins']}**"
    )
    await safe_edit_or_send(callback, text, shop_keyboard())
    await callback.answer("Покупка успешна!")


def build_faction_text(user: dict) -> str:
    fac_key = user.get("faction")
    lines = [
        "🏴 **Фракции и лидерка**\n",
        f"Твой статус: **{get_faction_label(user)}**\n",
    ]
    for key, f in FACTIONS.items():
        leader_gid = faction_leaders.get(key)
        leader_user = get_user_by_game_id(leader_gid) if leader_gid else None
        leader_str = (
            f"{leader_user['name']} (`ID: {leader_gid}`)"
            if leader_user
            else "не назначен"
        )
        members_count = sum(1 for u in users.values() if u.get("faction") == key)
        lines.append(
            f"• **{f['name']}** ({f['desc']})\n"
            f"  👑 Лидер: {leader_str} | 👥 Участников: **{members_count}**"
        )

    if fac_key and fac_key in FACTIONS:
        members = [
            f"`{u['game_id']}` — {u['name']} (Ур. {u.get('level', 1)})"
            for u in users.values()
            if u.get("faction") == fac_key
        ][:12]
        lines.append("\n**Участники твоей фракции:**")
        lines.append("\n".join(members) if members else "пока никого")

    return "\n".join(lines)


@dp.callback_query(F.data == "menu_faction")
async def on_menu_faction(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    await safe_edit_or_send(callback, build_faction_text(user), faction_keyboard(user))
    await callback.answer()


@dp.callback_query(F.data.startswith("set_faction_"))
async def on_set_faction(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    fac_key = callback.data.removeprefix("set_faction_")
    if fac_key not in FACTIONS:
        await callback.answer("Фракция не найдена", show_alert=True)
        return

    old_fac = user.get("faction")
    if old_fac and faction_leaders.get(old_fac) == user["game_id"] and old_fac != fac_key:
        faction_leaders.pop(old_fac, None)

    user["faction"] = fac_key
    new_max_hp = get_max_hp(user)
    if user.get("hp", MAX_HP) > new_max_hp:
        user["hp"] = new_max_hp
    save_data()

    await safe_edit_or_send(
        callback,
        f"✅ Ты вступил во фракцию **{FACTIONS[fac_key]['name']}**!\n\n{build_faction_text(user)}",
        faction_keyboard(user),
    )
    await callback.answer("Фракция выбрана")


@dp.callback_query(F.data == "leave_faction")
async def on_leave_faction(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    old_fac = user.get("faction")
    if not old_fac:
        await callback.answer("Ты не состоишь во фракции", show_alert=True)
        return

    if faction_leaders.get(old_fac) == user["game_id"]:
        faction_leaders.pop(old_fac, None)

    user["faction"] = None
    new_max_hp = get_max_hp(user)
    if user.get("hp", MAX_HP) > new_max_hp:
        user["hp"] = new_max_hp
    save_data()

    await safe_edit_or_send(
        callback,
        f"🚪 Ты покинул фракцию **{FACTIONS[old_fac]['name']}**.\n\n{build_faction_text(user)}",
        faction_keyboard(user),
    )
    await callback.answer("Ты вышел из фракции")


@dp.callback_query(F.data == "ldr_bonus")
async def on_ldr_bonus(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    if not is_faction_leader(user):
        await callback.answer("Только лидер фракции может выдавать премию!", show_alert=True)
        return

    now = time.time()
    rem = int(LEADER_BONUS_COOLDOWN - (now - user.get("last_leader_bonus", 0.0)))
    if rem > 0:
        await callback.answer(f"⏳ Кулдаун премии: ещё {rem} сек.", show_alert=True)
        return

    await state.set_state(GameStates.waiting_leader_bonus)
    await callback.message.answer("🎁 Введи **игровой ID** участника своей фракции для выдачи премии (+25 монет):", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_leader_bonus)
async def on_ldr_bonus_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    leader = get_user(uid, message.from_user.first_name)
    if not is_faction_leader(leader):
        await state.clear()
        await message.answer("⛔ Ты больше не лидер фракции.")
        return

    try:
        target_gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи корректный числовой игровой ID.")
        return

    target = get_user_by_game_id(target_gid)
    if not target or target.get("faction") != leader.get("faction"):
        await message.answer("Игрок с таким ID не найден в твоей фракции.")
        return

    target["coins"] = target.get("coins", 0) + 25
    leader["last_leader_bonus"] = time.time()
    save_data()
    await state.clear()
    await message.answer(f"✅ Выдана премия **+25 монет** игроку **{target['name']}** (`ID: {target_gid}`).", parse_mode="Markdown")


@dp.callback_query(F.data == "ldr_kick")
async def on_ldr_kick(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    if not is_faction_leader(user):
        await callback.answer("Только лидер фракции может исключать участников!", show_alert=True)
        return
    await state.set_state(GameStates.waiting_leader_kick)
    await callback.message.answer("👢 Введи **игровой ID** участника, которого нужно исключить из фракции:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_leader_kick)
async def on_ldr_kick_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    leader = get_user(uid, message.from_user.first_name)
    if not is_faction_leader(leader):
        await state.clear()
        return

    try:
        target_gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой игровой ID.")
        return

    if target_gid == leader["game_id"]:
        await message.answer("Нельзя исключить самого себя.")
        return

    target = get_user_by_game_id(target_gid)
    if not target or target.get("faction") != leader.get("faction"):
        await message.answer("Игрок с таким ID не состоит в твоей фракции.")
        return

    target["faction"] = None
    new_max_hp = get_max_hp(target)
    if target.get("hp", MAX_HP) > new_max_hp:
        target["hp"] = new_max_hp
    save_data()
    await state.clear()
    await message.answer(f"👢 Игрок **{target['name']}** (`ID: {target_gid}`) исключён из фракции.", parse_mode="Markdown")


@dp.callback_query(F.data == "menu_top")
async def on_menu_top(callback: CallbackQuery):
    top_users = sorted(
        users.values(),
        key=lambda u: (u.get("level", 1), u.get("coins", 0)),
        reverse=True,
    )[:10]

    lines = ["🏆 **Топ-10 игроков**\n"]
    for idx, u in enumerate(top_users, start=1):
        lines.append(
            f"{idx}. **{u.get('name', 'Игрок')}** (`ID: {u['game_id']}`) — "
            f"Ур. **{u.get('level', 1)}** | 💰 **{u.get('coins', 0)}**"
        )
    if not top_users:
        lines.append("Пока нет игроков.")

    await safe_edit_or_send(callback, "\n".join(lines), back_keyboard())
    await callback.answer()


# --- ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИГРОКОВ ---

@dp.callback_query(F.data == "menu_extra")
async def on_menu_extra(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    text = (
        "🎮 **Игровые функции**\n\n"
        f"💰 Баланс: **{user.get('coins', 0)}** монет | 🆔 Твой ID: **`{user['game_id']}`**\n"
        "Выбери действие:"
    )
    await safe_edit_or_send(callback, text, extra_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "act_daily")
async def on_daily(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    now = time.time()
    last_daily = float(user.get("last_daily", 0.0))
    elapsed = now - last_daily

    if last_daily > 0 and elapsed < DAILY_COOLDOWN:
        rem = int(DAILY_COOLDOWN - elapsed)
        hours = rem // 3600
        mins = (rem % 3600) // 60
        await callback.answer(f"⏳ Ежедневка будет доступна через {hours}ч {mins}м", show_alert=True)
        return

    if last_daily > 0 and elapsed <= DAILY_STREAK_WINDOW:
        streak = int(user.get("daily_streak", 0)) + 1
    else:
        streak = 1

    streak_capped = min(streak, 10)
    reward_coins = 50 + (streak_capped - 1) * 15
    reward_xp = 15 + (streak_capped - 1) * 5

    user["last_daily"] = now
    user["daily_streak"] = streak
    user["coins"] = int(user.get("coins", 0)) + reward_coins
    leveled = add_xp(user, reward_xp)
    save_data()

    note = (
        f"📅 **Ежедневный бонус получен!**\n"
        f"🔥 Серия входов: **{streak}** дн.\n"
        f"Награда: **+{reward_coins}** монет и **+{reward_xp} XP**."
    )
    if leveled:
        note += f"\n🎉 **Новый уровень: {user['level']}!**"

    await safe_edit_or_send(callback, format_profile(user, note), main_keyboard(uid))
    await callback.answer(f"+{reward_coins} монет")


@dp.callback_query(F.data == "act_transfer")
async def on_transfer_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameStates.waiting_transfer_input)
    await callback.message.answer(
        "💸 Введи **игровой ID** получателя и **сумму монет** через пробел:\n"
        "Пример: `1002 150`",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(GameStates.waiting_transfer_input)
async def on_transfer_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    sender = get_user(uid, message.from_user.first_name)
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <сумма>`", parse_mode="Markdown")
        return

    try:
        target_gid = int(parts[0])
        amount = int(parts[1])
    except ValueError:
        await message.answer("ID и сумма должны быть целыми числами.")
        return

    if amount <= 0:
        await message.answer("Сумма перевода должна быть больше нуля.")
        return

    if target_gid == sender["game_id"]:
        await message.answer("Нельзя перевести монеты самому себе.")
        return

    target = get_user_by_game_id(target_gid)
    if not target:
        await message.answer("Игрок с таким ID не найден.")
        return

    if int(sender.get("coins", 0)) < amount:
        await message.answer("Недостаточно монет на балансе.")
        return

    sender["coins"] = int(sender.get("coins", 0)) - amount
    target["coins"] = int(target.get("coins", 0)) + amount
    save_data()
    await state.clear()

    await message.answer(
        f"✅ Переведено **{amount}** монет игроку **{target['name']}** (`ID: {target_gid}`).\n"
        f"💰 Твой новый баланс: **{sender['coins']}**.",
        parse_mode="Markdown",
    )
    try:
        await bot.send_message(
            target["tg_id"],
            f"💸 Ты получил перевод **+{amount}** монет от **{sender['name']}** (`ID: {sender['game_id']}`).",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@dp.callback_query(F.data == "act_duel")
async def on_duel_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameStates.waiting_duel_input)
    await callback.message.answer(
        "⚔️ Введи **игровой ID** соперника и **ставку монет** через пробел:\n"
        "Пример: `1002 50`",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(GameStates.waiting_duel_input)
async def on_duel_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    p1 = get_user(uid, message.from_user.first_name)
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <ставка>`", parse_mode="Markdown")
        return

    try:
        target_gid = int(parts[0])
        bet = int(parts[1])
    except ValueError:
        await message.answer("ID и ставка должны быть целыми числами.")
        return

    if bet < 10:
        await message.answer("Минимальная ставка для дуэли — 10 монет.")
        return

    if target_gid == p1["game_id"]:
        await message.answer("Нельзя вызвать на дуэль самого себя.")
        return

    p2 = get_user_by_game_id(target_gid)
    if not p2:
        await message.answer("Соперник с таким ID не найден.")
        return

    if int(p1.get("coins", 0)) < bet:
        await message.answer("У тебя не хватает монет для этой ставки.")
        return

    if int(p2.get("coins", 0)) < bet:
        await message.answer("У соперника не хватает монет для этой ставки.")
        return

    fac1 = FACTIONS.get(p1.get("faction") or "")
    fac2 = FACTIONS.get(p2.get("faction") or "")
    power1 = (
        int(p1.get("level", 1)) * 4
        + int(p1.get("power_bonus", 0))
        + (fac1["work_bonus"] if fac1 else 0)
        + random.randint(1, 25)
    )
    power2 = (
        int(p2.get("level", 1)) * 4
        + int(p2.get("power_bonus", 0))
        + (fac2["work_bonus"] if fac2 else 0)
        + random.randint(1, 25)
    )

    if power1 >= power2:
        winner, loser = p1, p2
    else:
        winner, loser = p2, p1

    winner["coins"] = int(winner.get("coins", 0)) + bet
    loser["coins"] = int(loser.get("coins", 0)) - bet
    leveled = add_xp(winner, 15)
    save_data()
    await state.clear()

    lvl_text = f"\n🎉 **{winner['name']}** поднял уровень до **{winner['level']}**!" if leveled else ""
    await message.answer(
        f"⚔️ **Дуэль завершена!**\n"
        f"🏆 Победитель: **{winner['name']}** (`ID: {winner['game_id']}`) забирает **+{bet}** монет и **+15 XP**!\n"
        f"💔 Проигравший: **{loser['name']}** (`ID: {loser['game_id']}`) теряет **-{bet}** монет.{lvl_text}",
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "act_slots")
async def on_slots_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameStates.waiting_slots_bet)
    await callback.message.answer(
        "🎰 Введи **ставку монет** для слотов (минимум 10):",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(GameStates.waiting_slots_bet)
async def on_slots_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    try:
        bet = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи целое число — сумму ставки.")
        return

    if bet < 10:
        await message.answer("Минимальная ставка — 10 монет.")
        return

    if int(user.get("coins", 0)) < bet:
        await message.answer("Недостаточно монет на балансе.")
        return

    symbols = ["🍒", "🍋", "💎", "7️⃣"]
    reels = [random.choice(symbols) for _ in range(3)]
    reel_str = " | ".join(reels)

    user["coins"] = int(user.get("coins", 0)) - bet
    if reels[0] == reels[1] == reels[2]:
        mult = 5 if reels[0] == "7️⃣" else 3
        payout = bet * mult
        user["coins"] = int(user.get("coins", 0)) + payout
        add_xp(user, 10)
        res_text = f"🎉 **ДЖЕКПОТ (x{mult})!** Выигрыш **+{payout}** монет и **+10 XP**!"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        payout = max(1, int(bet * 1.5))
        user["coins"] = int(user.get("coins", 0)) + payout
        res_text = f"✨ **Пара совпала!** Возврат/выигрыш **+{payout}** монет."
    else:
        res_text = f"💨 Мимо! Потеряно **{bet}** монет."

    save_data()
    await state.clear()
    await message.answer(
        f"🎰 `[ {reel_str} ]`\n\n{res_text}\n💰 Баланс: **{user['coins']}**",
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "menu_quest")
async def on_menu_quest(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    done = int(user.get("quests_done", 0))
    claimed = bool(user.get("quest_claimed", False))
    progress = min(done, QUEST_TARGET_ACTIONS)

    if claimed:
        status = "✅ Награда за квест уже получена."
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboard
Button(text="⬅️ Назад", callback_data="menu_extra")]]
        )
    elif done >= QUEST_TARGET_ACTIONS:
        status = "🎁 Квест выполнен! Жми кнопку ниже, чтобы забрать награду."
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Забрать награду", callback_data="claim_quest")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_extra")],
            ]
        )
    else:
        status = f"⏳ Прогресс: **{progress}/{QUEST_TARGET_ACTIONS}** активностей (работа или риск-бросок)."
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_extra")]]
        )

    text = (
        "📜 **Квест игрока**\n\n"
        f"Цель: сделать **{QUEST_TARGET_ACTIONS}** вылазок или риск-бросков.\n"
        f"Награда: **+{QUEST_REWARD_COINS}** монет и **+{QUEST_REWARD_XP} XP**.\n\n"
        f"{status}"
    )
    await safe_edit_or_send(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data == "claim_quest")
async def on_claim_quest(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    if bool(user.get("quest_claimed", False)):
        await callback.answer("Награда уже получена.", show_alert=True)
        return
    if int(user.get("quests_done", 0)) < QUEST_TARGET_ACTIONS:
        await callback.answer("Квест ещё не выполнен.", show_alert=True)
        return

    user["quest_claimed"] = True
    user["coins"] = int(user.get("coins", 0)) + QUEST_REWARD_COINS
    leveled = add_xp(user, QUEST_REWARD_XP)
    save_data()

    extra = f"\n🎉 Новый уровень: **{user['level']}**!" if leveled else ""
    await safe_edit_or_send(
        callback,
        f"✅ Награда получена: **+{QUEST_REWARD_COINS}** монет и **+{QUEST_REWARD_XP} XP**!{extra}",
        extra_keyboard(),
    )
    await callback.answer("Награда получена!")


@dp.callback_query(F.data == "act_lookup")
async def on_lookup_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameStates.waiting_lookup_gid)
    await callback.message.answer("🔍 Введи **игровой ID** игрока для просмотра его карточки:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_lookup_gid)
async def on_lookup_input(message: Message, state: FSMContext):
    try:
        gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой игровой ID.")
        return

    target = get_user_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким ID не найден.")
        return

    max_hp = get_max_hp(target)
    await state.clear()
    await message.answer(
        f"🔍 **Карточка игрока**\n\n"
        f"👤 Имя: **{target.get('name', 'Игрок')}**\n"
        f"🆔 Игровой ID: **`{target['game_id']}`**\n"
        f"🏴 Фракция: **{get_faction_label(target)}**\n"
        f"🏅 Уровень: **{target.get('level', 1)}**\n"
        f"💰 Монеты: **{target.get('coins', 0)}**\n"
        f"❤️ HP: **{target.get('hp', max_hp)}/{max_hp}**\n"
        f"⚡ Бонус силы: **+{target.get('power_bonus', 0)}**",
        parse_mode="Markdown",
    )


# --- СИСТЕМА ПРОМОКОДОВ И МЕДИА ---

@dp.callback_query(F.data == "act_promo")
async def on_act_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GameStates.waiting_activate_promo)
    await callback.message.answer("🎟 Введи промокод для активации:")
    await callback.answer()


@dp.message(GameStates.waiting_activate_promo)
async def on_activate_promo_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    code = (message.text or "").strip().upper()
    promo = promo_codes.get(code)
    if not promo:
        await state.clear()
        await message.answer("❌ Такого промокода не существует.")
        return

    used_promos = user.setdefault("used_promos", [])
    if code in used_promos:
        await state.clear()
        await message.answer("⚠️ Ты уже активировал этот промокод.")
        return

    uses = int(promo.get("uses", 0))
    max_uses = int(promo.get("max_uses", 1))
    if uses >= max_uses:
        await state.clear()
        await message.answer("❌ Лимит активаций этого промокода исчерпан.")
        return

    reward_coins = int(promo.get("coins", 0))
    promo["uses"] = uses + 1
    used_promos.append(code)
    user["coins"] = int(user.get("coins", 0)) + reward_coins
    save_data()
    await state.clear()
    await message.answer(
        f"✅ Промокод `{code}` активирован! Получено **+{reward_coins}** монет.",
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "media_panel")
async def on_media_panel(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_media(uid):
        await callback.answer("⛔ Нет доступа к медиа-панели.", show_alert=True)
        return
    await state.clear()
    await safe_edit_or_send(callback, "🎬 **Медиа-панель**\n\nВыбери действие:", media_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "med_reward")
async def on_med_reward(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_media(uid):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    user = get_user(uid, callback.from_user.first_name)
    now = time.time()
    left =  int(MEDIA_REWARD_COOLDOWN - (now - float(user.get("last_media_reward", 0.0))))
    if left > 0:
        await callback.answer(f"⏳ Подожди ещё {left} сек.", show_alert=True)
        return

    await state.set_state(GameStates.waiting_media_reward_gid)
    await callback.message.answer("🎁 Введи **игровой ID** игрока, которому хочешь выдать медиа-награду:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_media_reward_gid)
async def on_med_reward_gid_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not is_media(uid):
        await state.clear()
        return
    try:
        target_gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи корректный числовой игровой ID.")
        return

    target = get_user_by_game_id(target_gid)
    if not target:
        await message.answer("Игрок с таким ID не найден.")
        return

    media_user = get_user(uid, message.from_user.first_name)
    now = time.time()
    if now - float(media_user.get("last_media_reward", 0.0)) < MEDIA_REWARD_COOLDOWN:
        await state.clear()
        await message.answer("⏳ Кулдаун выдачи медиа-награды ещё не прошёл.")
        return

    target["coins"] = int(target.get("coins", 0)) + MEDIA_REWARD_COINS
    add_xp(target, MEDIA_REWARD_XP)
    media_user["last_media_reward"] = now
    save_data()
    await state.clear()
    await message.answer(
        f"✅ Игроку **{target['name']}** (`ID: {target_gid}`) выдано **+{MEDIA_REWARD_COINS}** монет и **+{MEDIA_REWARD_XP} XP**.",
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "med_create_promo")
async def on_med_create_promo(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_media(uid):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(GameStates.waiting_create_promo)
    await callback.message.answer(
        "🎟 Введи промокод, сумму монет и лимит активаций через пробел:\n"
        "`КОД МОНЕТЫ ЛИМИТ`\n"
        "Пример: `STREAM100 500 50`",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(GameStates.waiting_create_promo)
async def on_med_create_promo_input(message: Message, state: FSMContext):
    uid = message.from_user.id
    if not is_media(uid):
        await state.clear()
        return

    parts = (message.text or "").strip().split()
    if len(parts) != 3:
        await message.answer("Формат: `КОД МОНЕТЫ ЛИМИТ`", parse_mode="Markdown")
        return

    code = parts[0].upper()
    try:
        coins = int(parts[1])
        max_uses = int(parts[2])
    except ValueError:
        await message.answer("Монеты и лимит должны быть целыми числами.")
        return

    if coins <= 0 or max_uses <= 0:
        await message.answer("Значения должны быть больше нуля.")
        return

    creator = get_user(uid, message.from_user.first_name)
    promo_codes[code] = {
        "coins": coins,
        "uses": 0,
        "max_uses": max_uses,
        "creator_gid": int(creator.get("game_id", 0)),
    }
    save_data()
    await state.clear()
    await message.answer(
        f"✅ Промокод `{code}` создан: **{coins}** монет, лимит **{max_uses}** активаций.",
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "med_stats")
async def on_med_stats(callback: CallbackQuery):
    uid = callback.from_user.id
    if not is_media(uid):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    user = get_user(uid, callback.from_user.first_name)
    gid = int(user.get("game_id", 0))
    own_promos = [
        f"• `{code}`: {info.get('uses', 0)}/{info.get('max_uses', 1)} ({info.get('coins', 0)} монет)"
        for code, info in promo_codes.items()
        if int(info.get("creator_gid", 0)) == gid
    ]
    promos_text = "\n".join(own_promos) if own_promos else "Пока нет созданных промокодов."
    await safe_edit_or_send(
        callback,
        f"📊 **Статистика медиа**\n\nТвои промокоды:\n{promos_text}",
        media_keyboard(),
    )
    await callback.answer()


# --- АДМИН-ПАНЕЛЬ ---

@dp.callback_query(F.data == "admin_panel")
async def on_admin_panel(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_admin(uid):
        await callback.answer("⛔ Нет доступа к админ-панели", show_alert=True)
        return
    await state.clear()
    await safe_edit_or_send(
        callback,
        "🛠 **Админ-панель** (все действия по игровому ID)\nВыбери действие:",
        admin_keyboard(uid),
    )
    await callback.answer()


@dp.callback_query(F.data == "adm_cancel")
async def on_adm_cancel(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_admin(uid):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.clear()
    await safe_edit_or_send(callback, "❌ Ввод отменён.\n\n🛠 **Админ-панель**:", admin_keyboard(uid))
    await callback.answer()


@dp.callback_query(F.data == "adm_stats")
async def on_adm_stats(callback: CallbackQuery):
    uid = callback.from_user.id
    if not is_admin(uid):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    total_users = len(users)
    total_coins = sum(u.get("coins", 0) for u in users.values())
    text = (
        "📊 **Статистика бота**\n\n"
        f"👥 Игроков: **{total_users}**\n"
        f"💰 Всего монет в экономике: **{total_coins}**\n"
        f"🛡 Админов (по ID): **{len(admins)}**\n"
        f"🎬 Медиа: **{len(media_creators)}**\n"
        f"🎟 Промокодов: **{len(promo_codes)}**"
    )
    await safe_edit_or_send(callback, text, admin_keyboard(uid))
    await callback.answer()


@dp.callback_query(F.data == "adm_media_role")
async def on_adm_media_role(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if not is_admin(uid):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_toggle_media)
    await callback.message.answer("🎬 Введи **игровой ID** пользователя для выдачи или снятия медиа-роли:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_toggle_media)
async def on_toggle_media_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        target_gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой игровой ID.")
        return

    target_tg = game_to_tg.get(target_gid)
    if target_tg is None:
        await message.answer("Игрок с таким ID не найден.")
        return

    if target_tg in media_creators:
        media_creators.remove(target_tg)
        status_text = f"🗑 Медиа-роль снята с игрока `ID: {target_gid}`."
    else:
        media_creators.add(target_tg)
        status_text = f"✅ Медиа-роль выдана игроку `ID: {target_gid}`."

    save_data()
    await state.clear()
    await message.answer(status_text, parse_mode="Markdown")


@dp.callback_query(F.data == "adm_give_coins")
async def on_adm_give_coins(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_give_coins)
    await callback.message.answer("💰 Введи: `<игровой_ID> <сумма>` (например: `1001 500`)", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_give_coins)
async def on_adm_give_coins_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <сумма>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
        amount = int(parts[1])
    except ValueError:
        await message.answer("ID и сумма должны быть целыми числами.")
        return
    target = get_user_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким ID не найден.")
        return
    target["coins"] = target.get("coins", 0) + amount
    save_data()
    await state.clear()
    await message.answer(f"✅ Игроку `{gid}` изменено монет на `{amount}` (теперь: {target['coins']}).", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_give_hp")
async def on_adm_give_hp(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_give_hp)
    await callback.message.answer("❤️ Введи: `<игровой_ID> <HP>` (например: `1001 50`)", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_give_hp)
async def on_adm_give_hp_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <HP>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
        delta_hp = int(parts[1])
    except ValueError:
        await message.answer("ID и HP должны быть целыми числами.")
        return
    target = get_user_by_game_id(gid)
    if not target:
        await message.answer("Игрок с таким ID не найден.")
        return
    max_hp = get_max_hp(target)
    target["hp"] = max(1, min(max_hp, target.get("hp", max_hp) + delta_hp))
    save_data()
    await state.clear()
    await message.answer(f"✅ Игроку `{gid}` задано HP: `{target['hp']}/{max_hp}`.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_set_level")
async def on_adm_set_level(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_set_level)
    await callback.message.answer("⭐ Введи: `<игровой_ID> <уровень>`", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_set_level)
async def on_adm_set_level_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <уровень>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
        lvl = int(parts[1])
    except ValueError:
        await message.answer("Введи числа.")
        return
    target = get_user_by_game_id(gid)
    if not target or lvl < 1:
        await message.answer("Игрок не найден или уровень < 1.")
        return
    target["level"] = lvl
    target["xp"] = 0
    target["hp"] = get_max_hp(target)
    save_data()
    await state.clear()
    await message.answer(f"✅ Игроку `{gid}` установлен уровень `{lvl}`.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_give_item")
async def on_adm_give_item(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_give_item)
    await callback.message.answer("🎒 Введи: `<игровой_ID> <medkit|amulet|blade>`", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_give_item)
async def on_adm_give_item_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <medkit|amulet|blade>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    item = SHOP_ITEMS.get(parts[1].lower())
    target = get_user_by_game_id(gid)
    if not target or not item:
        await message.answer("Игрок или предмет не найден.")
        return
    if "bonus" in item:
        target["power_bonus"] = target.get("power_bonus", 0) + item["bonus"]
    target.setdefault("items", []).append(item["name"])
    save_data()
    await state.clear()
    await message.answer(f"✅ Игроку `{gid}` выдан предмет **{item['name']}**.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_set_faction")
async def on_adm_set_faction(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_set_faction)
    await callback.message.answer("🏴 Введи: `<игровой_ID> <guards|seekers|bastion|none>`", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_set_faction)
async def on_adm_set_faction_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <guards|seekers|bastion|none>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    target = get_user_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    fac = parts[1].lower()
    if fac == "none":
        old_fac = target.get("faction")
        if old_fac and faction_leaders.get(old_fac) == gid:
            faction_leaders.pop(old_fac, None)
        target["faction"] = None
    elif fac in FACTIONS:
        old_fac = target.get("faction")
        if old_fac and faction_leaders.get(old_fac) == gid and old_fac != fac:
            faction_leaders.pop(old_fac, None)
        target["faction"] = fac
    else:
        await message.answer("Неверная фракция. Используй: `guards`, `seekers`, `bastion` или `none`.", parse_mode="Markdown")
        return
    new_max_hp = get_max_hp(target)
    if target.get("hp", MAX_HP) > new_max_hp:
        target["hp"] = new_max_hp
    save_data()
    await state.clear()
    await message.answer(f"✅ Фракция игрока `{gid}` обновлена.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_set_leader")
async def on_adm_set_leader(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_set_leader)
    await callback.message.answer("👑 Введи: `<игровой_ID> <guards|seekers|bastion|none>`", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_set_leader)
async def on_adm_set_leader_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<игровой_ID> <guards|seekers|bastion|none>`", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    target = get_user_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    fac = parts[1].lower()
    if fac == "none":
        for k, v in list(faction_leaders.items()):
            if v == gid:
                faction_leaders.pop(k, None)
        save_data()
        await state.clear()
        await message.answer(f"✅ Лидерство снято с игрока `{gid}`.", parse_mode="Markdown")
        return
    if fac not in FACTIONS:
        await message.answer("Неверная фракция.")
        return
    target["faction"] = fac
    faction_leaders[fac] = gid
    save_data()
    await state.clear()
    await message.answer(f"✅ Игрок `{gid}` назначен лидером **{FACTIONS[fac]['name']}**.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_set_id")
async def on_adm_set_id(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_set_game_id)
    await callback.message.answer("🆔 Введи: `<старый_ID> <новый_ID>`", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_set_game_id)
async def on_adm_set_id_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Формат: `<старый_ID> <новый_ID>`", parse_mode="Markdown")
        return
    try:
        old_gid = int(parts[0])
        new_gid = int(parts[1])
    except ValueError:
        await message.answer("ID должны быть числами.")
        return
    if new_gid <= 0 or new_gid in game_to_tg:
        await message.answer("Новый ID некорректен или уже занят.")
        return
    target = get_user_by_game_id(old_gid)
    if not target:
        await message.answer("Игрок со старым ID не найден.")
        return

    tg_id = target["tg_id"]
    game_to_tg.pop(old_gid, None)
    game_to_tg[new_gid] = tg_id
    target["game_id"] = new_gid
    if old_gid in admins:
        admins.remove(old_gid)
        admins.add(new_gid)
    for k, v in list(faction_leaders.items()):
        if v == old_gid:
            faction_leaders[k] = new_gid

    save_data()
    await state.clear()
    await message.answer(f"✅ Игровой ID изменён: `{old_gid}` → `{new_gid}`.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_reset_user")
async def on_adm_reset_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_reset_confirm)
    await callback.message.answer("🔄 Введи **игровой ID** игрока для полного сброса профиля:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_reset_confirm)
async def on_adm_reset_user_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    try:
        gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой игровой ID.")
        return
    target = get_user_by_game_id(gid)
    if not target:
        await message.answer("Игрок не найден.")
        return
    tg_id = target["tg_id"]
    name = target.get("name", "Игрок")
    for k, v in list(faction_leaders.items()):
        if v == gid:
            faction_leaders.pop(k, None)
    users[tg_id] = default_user_profile(tg_id, gid, name)
    save_data()
    await state.clear()
    await message.answer(f"✅ Профиль игрока `{gid}` сброшен.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_broadcast")
async def on_adm_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await state.set_state(GameStates.waiting_broadcast)
    await callback.message.answer("📢 Введи текст объявления для всех игроков:")
    await callback.answer()


@dp.message(GameStates.waiting_broadcast)
async def on_adm_broadcast_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст объявления не может быть пустым.")
        return
    sent = 0
    for tg_id in list(users.keys()):
        try:
            await bot.send_message(tg_id, f"📢 **Объявление:**\n\n{text}", parse_mode="Markdown")
            sent += 1
        except Exception:
            continue
    await state.clear()
    await message.answer(f"✅ Объявление отправлено `{sent}` игрокам.", parse_mode="Markdown")


@dp.callback_query(F.data == "adm_add_admin")
async def on_adm_add_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Только для владельца", show_alert=True)
        return
    await state.set_state(GameStates.waiting_add_admin)
    await callback.message.answer("➕ Введи **игровой ID** игрока для выдачи прав админа:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_add_admin)
async def on_adm_add_admin_input(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear()
        return
    try:
        gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой игровой ID.")
        return
    if gid not in game_to_tg:
        await message.answer("Игрок с таким ID не найден.")
        return
    admins.add(gid)
    save_data()
    await state.clear()
    await message.answer(f"✅ Игроку `{gid}` выданы права администратора.",
        parse_mode="Markdown")


@dp.callback_query(F.data == "adm_del_admin")
async def on_adm_del_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Только для владельца", show_alert=True)
        return
    await state.set_state(GameStates.waiting_remove_admin)
    await callback.message.answer("➖ Введи **игровой ID** игрока для снятия прав админа:", parse_mode="Markdown")
    await callback.answer()


@dp.message(GameStates.waiting_remove_admin)
async def on_adm_del_admin_input(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        await state.clear()
        return
    try:
        gid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введи числовой игровой ID.")
        return
    admins.discard(gid)
    save_data()
    await state.clear()
    await message.answer(f"✅ Права администратора сняты с игрока `{gid}`.", parse_mode="Markdown")


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в переменных окружения")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())





