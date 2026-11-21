import asyncio
import json
import logging
import os
import random
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

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 5516435343  # Твой числовой Telegram ID (без кавычек)

WORK_COOLDOWN = 20
LEADER_BONUS_COOLDOWN = 30
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

users: dict[int, dict] = {}             # tg_id -> данные игрока
game_to_tg: dict[int, int] = {}           # game_id -> tg_id
next_game_id: int = START_GAME_ID
admins: set[int] = set()                  # набор игровых ID админов
faction_leaders: dict[str, int] = {}      # faction_key -> game_id лидера


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
        "items": [],
        "power_bonus": 0,
        "faction": None,
    }


def load_data() -> None:
    global users, game_to_tg, next_game_id, admins, faction_leaders

    users = {}
    game_to_tg = {}
    admins = set()
    faction_leaders = {}
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


def is_owner(tg_id: int) -> bool:
    return tg_id == OWNER_ID


def is_admin(tg_id: int) -> bool:
    if is_owner(tg_id):
        return True
    user = users.get(tg_id)
    return bool(user and user["game_id"] in admins)


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
    elif name and users[tg_id].get("name") != name:
        users[tg_id]["name"] = name
        changed = True

    if changed:
        save_data()
    return users[tg_id]


def get_user_by_game_id(game_id: int) -> dict | None:
    tg_id = game_to_tg.get(game_id)
    if tg_id is None:
        return None
    return users.get(tg_id)


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

    if is_owner(user["tg_id"]):
        role_badge = "👑 Владелец"
    elif user["game_id"] in admins:
        role_badge = "🛡 Админ"
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
            InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_profile"),
        ],
    ]
    if is_admin(tg_id):
        rows.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    ]
    if is_owner(tg_id):
        rows.append([
            InlineKeyboardButton(text="➕ Дать админку", callback_data="adm_add_admin"),
            InlineKeyboardButton(text="➖ Снять админку", callback_data="adm_del_admin"),
        ])
    rows.append([InlineKeyboardButton(text="❌ Отмена ввода", callback_data="adm_cancel")])
    rows.append([InlineKeyboardButton(text="⬅️ В профиль", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
  await safe_edit_or_send(
      callback, build_faction_text(user), faction_keyboard(user)
  )
  await callback.answer()


@dp.callback_query(F.data.startswith("set_faction_"))
async def on_set_faction(callback: CallbackQuery):
  uid = callback.from_user.id
  user = get_user(uid, callback.from_user.first_name)
  fac_key = callback.data.removeprefix("set_faction_")
  fac = FACTIONS.get(fac_key)
  if not fac:
    await callback.answer("Фракция не найдена", show_alert=True)
    return

  old_fac = user.get("faction")
  if old_fac == fac_key:
    await callback.answer("Ты уже состоишь в этой фракции!", show_alert=True)
    return

  if old_fac and faction_leaders.get(old_fac) == user["game_id"]:
    del faction_leaders[old_fac]

  user["faction"] = fac_key
  max_hp = get_max_hp(user)
  if fac["hp_bonus"] > 0:
    user["hp"] = min(max_hp, user.get("hp", MAX_HP) + fac["hp_bonus"])
  else:
    user["hp"] = min(max_hp, user.get("hp", MAX_HP))

  save_data()
  await safe_edit_or_send(
      callback,
      f"✅ Ты вступил во фракцию **{fac['name']}**!\n\n"
      + build_faction_text(user),
      faction_keyboard(user),
  )
  await callback.answer("Фракция выбрана!")


@dp.callback_query(F.data == "leave_faction")
async def on_leave_faction(callback: CallbackQuery):
  uid = callback.from_user.id
  user = get_user(uid, callback.from_user.first_name)
  old_fac = user.get("faction")
  if not old_fac:
    await callback.answer("Ты не состоишь во фракции.", show_alert=True)
    return

  if faction_leaders.get(old_fac) == user["game_id"]:
    del faction_leaders[old_fac]

  user["faction"] = None
  user["hp"] = min(MAX_HP, user.get("hp", MAX_HP))
  save_data()

  await safe_edit_or_send(
      callback,
      "🚪 Ты покинул фракцию.\n\n" + build_faction_text(user),
      faction_keyboard(user),
  )
  await callback.answer("Вышел из фракции")


@dp.callback_query(F.data == "ldr_bonus")
async def on_ldr_bonus(callback: CallbackQuery, state: FSMContext):
  uid = callback.from_user.id
  user = get_user(uid, callback.from_user.first_name)
  if not is_faction_leader(user):
    await callback.answer("Доступно только лидеру фракции.", show_alert=True)
    return

  now = time.time()
  rem = int(LEADER_BONUS_COOLDOWN - (now - user.get("last_leader_bonus", 0.0)))
  if rem > 0:
    await callback.answer(
        f"⏳ Премию можно выдавать раз в {LEADER_BONUS_COOLDOWN} сек. Осталось"
        f" {rem} сек.",
        show_alert=True,
    )
    return

  await state.set_state(GameStates.waiting_leader_bonus)
  await callback.message.answer(
      "🎁 Введи **игровой ID** участника твоей фракции, которому выдать премию"
      " **+25 монет**:",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_leader_bonus)
async def process_leader_bonus(message: Message, state: FSMContext):
  leader = get_user(message.from_user.id, message.from_user.first_name)
  if not is_faction_leader(leader):
    await state.clear()
    return

  try:
    target_gid = int((message.text or "").strip())
  except ValueError:
    await message.answer(
        "⚠️ Введи числовой игровой ID.", parse_mode="Markdown"
    )
    return

  target = get_user_by_game_id(target_gid)
  if not target or target.get("faction") != leader.get("faction"):
    await message.answer(
        "⚠️ Игрок с таким ID не состоит в твоей фракции.", parse_mode="Markdown"
    )
    return

  leader["last_leader_bonus"] = time.time()
  target["coins"] = target.get("coins", 0) + 25
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Лидер выдал премию **+25 монет** игроку `{target_gid}`"
      f" (**{target['name']}**).",
      reply_markup=faction_keyboard(leader),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "ldr_kick")
async def on_ldr_kick(callback: CallbackQuery, state: FSMContext):
  uid = callback.from_user.id
  user = get_user(uid, callback.from_user.first_name)
  if not is_faction_leader(user):
    await callback.answer("Доступно только лидеру фракции.", show_alert=True)
    return

  await state.set_state(GameStates.waiting_leader_kick)
  await callback.message.answer(
      "👢 Введи **игровой ID** игрока, которого исключить из твоей фракции:",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_leader_kick)
async def process_leader_kick(message: Message, state: FSMContext):
  leader = get_user(message.from_user.id, message.from_user.first_name)
  if not is_faction_leader(leader):
    await state.clear()
    return

  try:
    target_gid = int((message.text or "").strip())
  except ValueError:
    await message.answer(
        "⚠️ Введи числовой игровой ID.", parse_mode="Markdown"
    )
    return

  if target_gid == leader["game_id"]:
    await message.answer(
        "⚠️ Нельзя исключить самого себя.", parse_mode="Markdown"
    )
    return

  target = get_user_by_game_id(target_gid)
  if not target or target.get("faction") != leader.get("faction"):
    await message.answer(
        "⚠️ Игрок с таким ID не состоит в твоей фракции.", parse_mode="Markdown"
    )
    return

  target["faction"] = None
  target["hp"] = min(MAX_HP, target.get("hp", MAX_HP))
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игрок `{target_gid}` (**{target['name']}**) исключён из фракции.",
      reply_markup=faction_keyboard(leader),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "menu_top")
async def on_menu_top(callback: CallbackQuery):
  if not users:
    await safe_edit_or_send(
        callback, "🏆 **Топ игроков**\n\nПока игроков нет.", back_keyboard()
    )
    await callback.answer()
    return

  ranked = sorted(
      users.values(),
      key=lambda u: (u.get("level", 1), u.get("coins", 0)),
      reverse=True,
  )[:10]

  lines = ["🏆 **Топ игроков**\n"]
  for idx, u in enumerate(ranked, start=1):
    medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"{idx}.")
    fac_short = (
        FACTIONS[u["faction"]]["name"]
        if u.get("faction") in FACTIONS
        else "Без фракции"
    )
    lines.append(
        f"{medal} **{u['name']}** (`ID: {u['game_id']}`) [{fac_short}] — Ур."
        f" {u.get('level', 1)} | 💰 {u.get('coins', 0)}"
    )

  await safe_edit_or_send(callback, "\n".join(lines), back_keyboard())
  await callback.answer()


@dp.callback_query(F.data == "admin_panel")
async def on_admin_panel(callback: CallbackQuery, state: FSMContext):
  uid = callback.from_user.id
  if not is_admin(uid):
    await callback.answer("Нет доступа", show_alert=True)
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
  await state.clear()
  uid = callback.from_user.id
  await safe_edit_or_send(
      callback, "🛠 **Админ-панель**\nВвод отменён.", admin_keyboard(uid)
  )
  await callback.answer("Отменено")


@dp.callback_query(F.data == "adm_broadcast")
async def on_adm_broadcast(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_broadcast)
  await callback.message.answer(
      "📢 Напиши текст объявления, который отправится **всем** игрокам бота\n"
      "(или нажми *Отмена ввода* в админ-панели):",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  text_body = (message.text or "").strip()
  if not text_body:
    await message.answer("⚠️ Текст объявления не может быть пустым.")
    return

  await state.clear()
  broadcast_text = f"📢 **Объявление от администрации:**\n\n{text_body}"
  sent_count = 0
  failed_count = 0

  for tg_id in list(users.keys()):
    try:
      await bot.send_message(tg_id, broadcast_text, parse_mode="Markdown")
      sent_count += 1
      await asyncio.sleep(0.05)
    except Exception:
      failed_count += 1

  await message.answer(
      f"✅ Рассылка завершена.\n"
      f"📨 Доставлено: **{sent_count}** | ⚠️ Ошибок: **{failed_count}**",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_stats")
async def on_adm_stats(callback: CallbackQuery):
  uid = callback.from_user.id
  if not is_admin(uid):
    await callback.answer("Нет доступа", show_alert=True)
    return
  total_users = len(users)
  total_coins = sum(u.get("coins", 0) for u in users.values())
  admins_list = ", ".join(str(x) for x in sorted(admins)) or "нет"
  leaders_info = (
      ", ".join(
          f"{FACTIONS[k]['name']}: `{v}`"
          for k, v in faction_leaders.items()
          if k in FACTIONS
      )
      or "нет"
  )
  players_preview = (
      "\n".join(
          f"• `{u['game_id']}` — {u['name']} (Ур. {u.get('level', 1)}, 💰"
          f" {u.get('coins', 0)}, ❤️ {u.get('hp', get_max_hp(u))})"
          for u in list(users.values())[:10]
      )
      or "нет игроков"
  )
  text = (
      f"📊 **Статистика**\n\n"
      f"👥 Игроков: **{total_users}**\n"
      f"💰 Всего монет: **{total_coins}**\n"
      f"🛡 Админы: `{admins_list}`\n"
      f"👑 Лидеры фракций: {leaders_info}\n\n"
      f"**Игроки:**\n{players_preview}"
  )
  await safe_edit_or_send(callback, text, admin_keyboard(uid))
  await callback.answer()


@dp.callback_query(F.data == "adm_set_level")
async def on_adm_set_level(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_set_level)
  await callback.message.answer(
      "⭐ Отправь: `ИГРОВОЙ_ID УРОВЕНЬ`\nПример: `1001 5`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_set_level)
async def process_set_level(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer(
        "⚠️ Формат: `ИГРОВОЙ_ID УРОВЕНЬ`.", parse_mode="Markdown"
    )
    return
  try:
    gid = int(parts[0])
    new_lvl = int(parts[1])
  except ValueError:
    await message.answer(
        "⚠️ ID и уровень должны быть целыми числами.", parse_mode="Markdown"
    )
    return

  if new_lvl < 1 or new_lvl > 999:
    await message.answer(
        "⚠️ Уровень должен быть от `1` до `999`.", parse_mode="Markdown"
    )
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
    )
    return

  target["level"] = new_lvl
  target["xp"] = 0
  target["hp"] = get_max_hp(target)
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игроку `{gid}` (**{target['name']}**) установлен уровень"
      f" **{new_lvl}** (HP восстановлено).",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_give_item")
async def on_adm_give_item(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_give_item)
  await callback.message.answer(
      "🎒 Отправь: `ИГРОВОЙ_ID КОД_ПРЕДМЕТА`\n"
      "Коды: `medkit` (аптечка), `amulet` (амулет +5), `blade` (клинок +12)\n"
      "Пример: `1001 blade`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_give_item)
async def process_give_item(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer(
        "⚠️ Формат: `ИГРОВОЙ_ID КОД_ПРЕДМЕТА`.", parse_mode="Markdown"
    )
    return
  try:
    gid = int(parts[0])
  except ValueError:
    await message.answer(
        "⚠️ Игровой ID должен быть целым числом.", parse_mode="Markdown"
    )
    return

  item_key = parts[1].lower()
  item = SHOP_ITEMS.get(item_key)
  if not item:
    await message.answer(
        "⚠️ Неверный код предмета. Доступны: `medkit`, `amulet`, `blade`.",
        parse_mode="Markdown",
    )
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
    )
    return

  max_hp = get_max_hp(target)
  extra_info = ""
  if "hp" in item:
    target["hp"] = min(max_hp, target.get("hp", max_hp) + item["hp"])
    extra_info = f" (HP: {target['hp']}/{max_hp})"
  elif "bonus" in item:
    target["power_bonus"] = target.get("power_bonus", 0) + item["bonus"]
    target.setdefault("items", []).append(item["name"])
    extra_info = f" (бонус силы: +{target['power_bonus']})"

  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игроку `{gid}` (**{target['name']}**) выдан **{item['name']}**{extra_info}.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_set_faction")
async def on_adm_set_faction(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_set_faction)
  await callback.message.answer(
      "🏴 Отправь: `ИГРОВОЙ_ID ФРАКЦИЯ`\n"
      "Фракции: `guards`, `seekers`, `bastion` или `none` (снять)\n"
      "Пример: `1001 seekers`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_set_faction)
async def process_set_faction_admin(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer(
        "⚠️ Формат: `ИГРОВОЙ_ID ФРАКЦИЯ`.", parse_mode="Markdown"
    )
    return
  try:
    gid = int(parts[0])
  except ValueError:
    await message.answer(
        "⚠️ Игровой ID должен быть целым числом.", parse_mode="Markdown"
    )
    return

  fac_arg = parts[1].lower()
  if fac_arg != "none" and fac_arg not in FACTIONS:
    await message.answer(
        "⚠️ Фракция должна быть `guards`, `seekers`, `bastion` или `none`.",
        parse_mode="Markdown",
    )
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
    )
    return

  old_fac = target.get("faction")
  if old_fac and faction_leaders.get(old_fac) == gid:
    del faction_leaders[old_fac]

  if fac_arg == "none":
    target["faction"] = None
    target["hp"] = min(MAX_HP, target.get("hp", MAX_HP))
    save_data()
    await state.clear()
    await message.answer(
        f"✅ Фракция снята с игрока `{gid}` (**{target['name']}**).",
        reply_markup=admin_keyboard(message.from_user.id),
        parse_mode="Markdown",
    )
    return

  target["faction"] = fac_arg
  max_hp = get_max_hp(target)
  if FACTIONS[fac_arg]["hp_bonus"] > 0:
    target["hp"] = min(
        max_hp, target.get("hp", MAX_HP) + FACTIONS[fac_arg]["hp_bonus"]
    )
  else:
    target["hp"] = min(max_hp, target.get("hp", MAX_HP))

  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игрок `{gid}` (**{target['name']}**) переведён во фракцию"
      f" **{FACTIONS[fac_arg]['name']}**.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_set_leader")
async def on_adm_set_leader(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_set_leader)
  await callback.message.answer(
      "👑 Отправь: `КОД_ФРАКЦИИ ИГРОВОЙ_ID`\nКоды фракций: `guards` (Стражи),"
      " `seekers` (Искатели), `bastion` (Бастион)\nПример назначения: `guards"
      " 1001`\nПример снятия: `guards 0`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_set_leader)
async def process_set_leader(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return

  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer(
        "⚠️ Формат: `КОД_ФРАКЦИИ ИГРОВОЙ_ID` (например `guards 1001`).",
        parse_mode="Markdown",
    )
    return

  fac_key = parts[0].lower()
  if fac_key not in FACTIONS:
    await message.answer(
        "⚠️ Неверный код фракции. Доступны: `guards`, `seekers`, `bastion`.",
        parse_mode="Markdown",
    )
    return

  try:
    gid = int(parts[1])
  except ValueError:
    await message.answer(
        "⚠️ Игровой ID должен быть целым числом.", parse_mode="Markdown"
    )
    return

    if gid == 0:
      faction_leaders.pop(fac_key, None)
      save_data()
      await state.clear()
      await message.answer(
          f"✅ Лидер фракции **{FACTIONS[fac_key]['name']}** снят.",
          reply_markup=admin_keyboard(message.from_user.id),
          parse_mode="Markdown",
      )
      return

    target = get_user_by_game_id(gid)
    if not target:
      await message.answer(
          f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
      )
      return

    old_fac = target.get("faction")
    if old_fac and old_fac != fac_key and faction_leaders.get(old_fac) == gid:
      del faction_leaders[old_fac]

    target["faction"] = fac_key
    max_hp = get_max_hp(target)
    target["hp"] = min(
        max_hp,
        max(
            target.get("hp", MAX_HP),
            max_hp
            if FACTIONS[fac_key]["hp_bonus"] > 0
            else target.get("hp", MAX_HP),
        ),
    )
    faction_leaders[fac_key] = gid
    save_data()

    await state.clear()
    await message.answer(
        f"✅ Игрок `{gid}` (**{target['name']}**) назначен лидером фракции"
        f" **{FACTIONS[fac_key]['name']}**!",
        reply_markup=admin_keyboard(message.from_user.id),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "adm_give_coins")
async def on_adm_give_coins(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_give_coins)
  await callback.message.answer(
      "💰 Отправь одним сообщением: `ИГРОВОЙ_ID СУММА`\nПример: `1001 500`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_give_coins)
async def process_give_coins(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer(
        "⚠️ Формат: `ИГРОВОЙ_ID СУММА`.", parse_mode="Markdown"
    )
    return
  try:
    gid = int(parts[0])
    amount = int(parts[1])
  except ValueError:
    await message.answer(
        "⚠️ Игровой ID и сумма должны быть целыми числами.",
        parse_mode="Markdown",
    )
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
    )
    return

  target["coins"] = target.get("coins", 0) + amount
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игроку `{gid}` (**{target['name']}**) изменено монет на"
      f" **{amount:+d}**. Баланс: **{target['coins']}**.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_give_hp")
async def on_adm_give_hp(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_give_hp)
  await callback.message.answer(
      "❤️ Отправь одним сообщением: `ИГРОВОЙ_ID HP`\nПример: `1001 30`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_give_hp)
async def process_give_hp(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer("⚠️ Формат: `ИГРОВОЙ_ID HP`.", parse_mode="Markdown")
    return
  try:
    gid = int(parts[0])
    amount = int(parts[1])
  except ValueError:
    await message.answer(
        "⚠️ Игровой ID и HP должны быть целыми числами.", parse_mode="Markdown"
    )
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
    )
    return

  max_hp = get_max_hp(target)
  target["hp"] = max(0, min(max_hp, target.get("hp", max_hp) + amount))
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игроку `{gid}` (**{target['name']}**) изменено HP на"
      f" **{amount:+d}**. Текущее HP: **{target['hp']}/{max_hp}**.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_set_id")
async def on_adm_set_id(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_set_game_id)
  await callback.message.answer(
      "🆔 Отправь одним сообщением: `СТАРЫЙ_ИГРОВОЙ_ID НОВЫЙ_ИГРОВОЙ_ID`\nПример:"
      " `1001 777`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_set_game_id)
async def process_set_game_id(message: Message, state: FSMContext):
  global next_game_id
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2:
    await message.answer(
        "⚠️ Формат: `СТАРЫЙ_ИГРОВОЙ_ID НОВЫЙ_ИГРОВОЙ_ID`.", parse_mode="Markdown"
    )
    return
  try:
    old_gid = int(parts[0])
    new_gid = int(parts[1])
  except ValueError:
    await message.answer(
        "⚠️ Оба ID должны быть целыми числами.", parse_mode="Markdown"
    )
    return

  target = get_user_by_game_id(old_gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с ID `{old_gid}` не найден.", parse_mode="Markdown"
    )
    return
  if new_gid in game_to_tg:
    await message.answer(
        f"⚠️ Игровой ID `{new_gid}` уже занят другим игроком.",
        parse_mode="Markdown",
    )
    return

  was_admin = old_gid in admins
  del game_to_tg[old_gid]
  target["game_id"] = new_gid
  game_to_tg[new_gid] = target["tg_id"]
  next_game_id = max(next_game_id, new_gid + 1)

  if was_admin:
    admins.discard(old_gid)
    admins.add(new_gid)

  for f_key, lgid in list(faction_leaders.items()):
    if lgid == old_gid:
      faction_leaders[f_key] = new_gid

  save_data()
  await state.clear()
  await message.answer(
      f"✅ Игровой ID для **{target['name']}** изменён: `{old_gid}` →"
      f" **`{new_gid}`**.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_reset_user")
async def on_adm_reset_user(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    await callback.answer("Нет доступа", show_alert=True)
    return
  await state.set_state(GameStates.waiting_reset_confirm)
  await callback.message.answer(
      "⚠️ Для сброса прогресса игрока отправь:\n`ПОДТВЕРДИТЬ ИГРОВОЙ_ID`\n"
      "Пример: `ПОДТВЕРДИТЬ 1002`",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_reset_confirm)
async def process_reset_user(message: Message, state: FSMContext):
  if not is_admin(message.from_user.id):
    await state.clear()
    return
  parts = (message.text or "").strip().split()
  if len(parts) != 2 or parts[0].upper() != "ПОДТВЕРДИТЬ":
    await message.answer(
        "⚠️ Формат: `ПОДТВЕРДИТЬ ИГРОВОЙ_ID`.", parse_mode="Markdown"
    )
    return
  try:
    gid = int(parts[1])
  except ValueError:
    await message.answer(
        "⚠️ Игровой ID должен быть целым числом.", parse_mode="Markdown"
    )
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown"
    )
    return

  old_fac = target.get("faction")
  if old_fac and faction_leaders.get(old_fac) == gid:
    del faction_leaders[old_fac]

  tg_id = target["tg_id"]
  name = target.get("name", "Игрок")
  users[tg_id] = default_user_profile(tg_id, gid, name)
  save_data()
  await state.clear()

  await message.answer(
      f"🔄 Прогресс игрока `{gid}` (**{name}**) сброшен до начального.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_add_admin")
async def on_adm_add_admin(callback: CallbackQuery, state: FSMContext):
  if not is_owner(callback.from_user.id):
    await callback.answer("Только главный владелец", show_alert=True)
    return
  await state.set_state(GameStates.waiting_add_admin)
  await callback.message.answer(
      "➕ Введи **игровой ID** игрока, которому выдать админку (например `1002`):",
      parse_mode="Markdown",
  )
  await callback.answer()


@dp.message(GameStates.waiting_add_admin)
async def process_add_admin(message: Message, state: FSMContext):
  if not is_owner(message.from_user.id):
    await state.clear()
    return
  try:
    gid = int((message.text or "").strip())
  except ValueError:
    await message.answer("⚠️ Нужен числовой игровой ID.", parse_mode="Markdown")
    return

  target = get_user_by_game_id(gid)
  if not target:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не найден. Пусть сначала нажмёт /start.",
        parse_mode="Markdown",
    )
    return

  admins.add(gid)
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Админка выдана игроку `{gid}` (**{target['name']}**).",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "adm_del_admin")
async def on_adm_del_admin(callback: CallbackQuery, state: FSMContext):
  if not is_owner(callback.from_user.id):
    await callback.answer("Только главный владелец", show_alert=True)
    return
  await state.set_state(GameStates.waiting_remove_admin)
  await callback.message.answer(
      "➖ Введи **игровой ID**, у которого снять админку:", parse_mode="Markdown"
  )
  await callback.answer()


@dp.message(GameStates.waiting_remove_admin)
async def process_remove_admin(message: Message, state: FSMContext):
  if not is_owner(message.from_user.id):
    await state.clear()
    return
  try:
    gid = int((message.text or "").strip())
  except ValueError:
    await message.answer("⚠️ Нужен числовой игровой ID.", parse_mode="Markdown")
    return

  if gid not in admins:
    await message.answer(
        f"⚠️ Игрок с игровым ID `{gid}` не является админом.", parse_mode="Markdown"
    )
    return

  admins.discard(gid)
  save_data()
  await state.clear()
  await message.answer(
      f"✅ Админка снята с игрового ID `{gid}`.",
      reply_markup=admin_keyboard(message.from_user.id),
      parse_mode="Markdown",
  )


async def main():
  while True:
    try:
      await bot.delete_webhook(drop_pending_updates=True)
      await dp.start_polling(bot, polling_timeout=30)
    except asyncio.CancelledError:
      break
    except Exception as e:
      logging.error(f"Сбой соединения: {e}. Перезапуск через 3 сек...")
      await asyncio.sleep(3)


if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    pass
