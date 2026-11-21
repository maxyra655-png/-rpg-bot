import asyncio
import logging
import random
import time
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 5516435343  # Твой числовой Telegram ID (без кавычек)

WORK_COOLDOWN = 20
MAX_HP = 100
START_GAME_ID = 1001

SHOP_ITEMS = {
    "medkit": {"name": "🩺 Аптечка (+35 HP)", "price": 40, "hp": 35},
    "amulet": {"name": "🛡 Амулет удачи (+5 к добыче)", "price": 120, "bonus": 5},
    "blade": {"name": "⚔️ Клинок рейда (+12 к добыче)", "price": 260, "bonus": 12},
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

users = {}          # tg_id -> данные игрока (включая game_id)
game_to_tg = {}     # game_id -> tg_id
next_game_id = START_GAME_ID
admins = set()      # набор игровых ID (game_id), у которых есть админка


class AdminStates(StatesGroup):
    waiting_give_coins = State()
    waiting_give_hp = State()
    waiting_set_game_id = State()
    waiting_add_admin = State()
    waiting_remove_admin = State()


def is_owner(tg_id: int) -> bool:
    return tg_id == OWNER_ID


def is_admin(tg_id: int) -> bool:
    if is_owner(tg_id):
        return True
    user = users.get(tg_id)
    return bool(user and user["game_id"] in admins)


def get_user(tg_id: int, name: str = "Игрок") -> dict:
    global next_game_id
    if tg_id not in users:
        while next_game_id in game_to_tg:
            next_game_id += 1
        gid = next_game_id
        next_game_id += 1

        users[tg_id] = {
            "tg_id": tg_id,
            "game_id": gid,
            "name": name or "Игрок",
            "coins": 0,
            "hp": MAX_HP,
            "xp": 0,
            "level": 1,
            "last_work": 0.0,
            "items": [],
            "power_bonus": 0,
        }
        game_to_tg[gid] = tg_id
    elif name:
        users[tg_id]["name"] = name
    return users[tg_id]


def get_user_by_game_id(game_id: int) -> dict | None:
    tg_id = game_to_tg.get(game_id)
    if tg_id is None:
        return None
    return users.get(tg_id)


def add_xp(user: dict, amount: int) -> bool:
    user["xp"] += amount
    leveled_up = False
    while user["xp"] >= user["level"] * 50:
        user["xp"] -= user["level"] * 50
        user["level"] += 1
        user["hp"] = MAX_HP
        leveled_up = True
    return leveled_up


def format_profile(user: dict, note: str = "") -> str:
    items_text = ", ".join(user["items"]) if user["items"] else "пусто"
    needed_xp = user["level"] * 50
    role_badge = "👑 Владелец" if is_owner(user["tg_id"]) else ("🛡 Админ" if user["game_id"] in admins else "🎮 Игрок")
    base_text = (
        f"🎮 **Профиль: {user['name']}** ({role_badge})\n"
        f"🆔 Игровой ID: **`{user['game_id']}`**\n\n"
        f"🏅 Уровень: **{user['level']}** (`{user['xp']}/{needed_xp} XP`)\n"
        f"💰 Монеты: **{user['coins']}**\n"
        f"❤️ HP: **{user['hp']}/{MAX_HP}**\n"
        f"⚡ Бонус силы: **+{user['power_bonus']}**\n"
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
            InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить профиль", callback_data="refresh_profile"),
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


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="back_main")]]
    )


def admin_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats"),
            InlineKeyboardButton(text="💰 Выдать монеты", callback_data="adm_give_coins"),
        ],
        [
            InlineKeyboardButton(text="❤️ Выдать HP", callback_data="adm_give_hp"),
            InlineKeyboardButton(text="🆔 Сменить ID", callback_data="adm_set_id"),
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
        format_profile(user, "👋 Добро пожаловать! У тебя есть свой игровой ID для всех действий."),
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
    rem = int(WORK_COOLDOWN - (now - user["last_work"]))
    if rem > 0:
        await callback.answer(f"⏳ Подожди ещё {rem} сек.", show_alert=True)
        return

    user["last_work"] = now
    earned = random.randint(15, 30) + user["power_bonus"]
    hp_loss = random.randint(3, 12)
    user["coins"] += earned
    user["hp"] = max(1, user["hp"] - hp_loss)
    leveled = add_xp(user, 15)

    note = f"⛏ Вылазка удалась! **+{earned}** монет, **-{hp_loss}** HP, **+15 XP**."
    if leveled:
        note += f"\n🎉 **Новый уровень: {user['level']}!** HP восстановлено до {MAX_HP}."

    await safe_edit_or_send(callback, format_profile(user, note), main_keyboard(uid))
    await callback.answer(f"+{earned} монет")


@dp.callback_query(F.data == "act_dice")
async def on_dice(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    bet = 20
    if user["coins"] < bet:
        await callback.answer("Нужно минимум 20 монет для риск-броска!", show_alert=True)
        return

    roll_val = random.randint(1, 6)
    if roll_val >= 4:
        win = 35 + user["power_bonus"]
        user["coins"] += win - bet
        leveled = add_xp(user, 10)
        note = f"🎲 Выпало **{roll_val}**! Победа: **+{win - bet}** монет и **+10 XP**."
        if leveled:
            note += f"\n🎉 **Новый уровень: {user['level']}!**"
    else:
        user["coins"] -= bet
        note = f"🎲 Выпало **{roll_val}**. Не повезло: потеряно **{bet}** монет."

    await safe_edit_or_send(callback, format_profile(user, note), main_keyboard(uid))
    await callback.answer(f"Выпало {roll_val}")


@dp.callback_query(F.data == "menu_shop")
async def on_menu_shop(callback: CallbackQuery):
    uid = callback.from_user.id
    user = get_user(uid, callback.from_user.first_name)
    text = (
        f"🛒 **Магазин**\n"
        f"💰 Твой баланс: **{user['coins']}** монет | ❤️ HP: **{user['hp']}/{MAX_HP}**\n\n"
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

    if user["coins"] < item["price"]:
        await callback.answer(f"Не хватает монет! Нужно {item['price']}.", show_alert=True)
        return

    user["coins"] -= item["price"]
    msg_extra = ""
    if "hp" in item:
        old_hp = user["hp"]
        user["hp"] = min(MAX_HP, user["hp"] + item["hp"])
        msg_extra = f"HP восстановлено: **{old_hp} → {user['hp']}**."
    elif "bonus" in item:
        user["power_bonus"] += item["bonus"]
        user["items"].append(item["name"])
        msg_extra = f"Бонус силы теперь **+{user['power_bonus']}**."

    text = (
        f"✅ Куплено: **{item['name']}**!\n"
        f"{msg_extra}\n"
        f"💰 Остаток монет: **{user['coins']}**"
    )
    await safe_edit_or_send(callback, text, shop_keyboard())
    await callback.answer("Покупка успешна!")


@dp.callback_query(F.data == "menu_top")
async def on_menu_top(callback: CallbackQuery):
    if not users:
        await safe_edit_or_send(callback, "🏆 **Топ игроков**\n\nПока игроков нет.", back_keyboard())
        await callback.answer()
        return

    ranked = sorted(
        users.values(),
        key=lambda u: (u["level"], u["coins"]),
        reverse=True,
    )[:10]

    lines = ["🏆 **Топ игроков**\n"]
    for idx, u in enumerate(ranked, start=1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"{idx}.")
        lines.append(f"{medal} **{u['name']}** (`ID: {u['game_id']}`) — Ур. {u['level']} | 💰 {u['coins']}")

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
    await safe_edit_or_send(callback, "🛠 **Админ-панель**\nВвод отменён.", admin_keyboard(uid))
    await callback.answer("Отменено")


@dp.callback_query(F.data == "adm_stats")
async def on_adm_stats(callback: CallbackQuery):
    uid = callback.from_user.id
    if not is_admin(uid):
        await callback.answer("Нет доступа", show_alert=True)
        return
    total_users = len(users)
    total_coins = sum(u["coins"] for u in users.values())
    admins_list = ", ".join(str(x) for x in sorted(admins)) or "нет"
    players_preview = "\n".join(
        f"• `{u['game_id']}` — {u['name']} (💰 {u['coins']}, ❤️ {u['hp']})"
        for u in list(users.values())[:10]
    ) or "нет игроков"
    text = (
        f"📊 **Статистика**\n\n"
        f"👥 Игроков: **{total_users}**\n"
        f"💰 Всего монет: **{total_coins}**\n"
        f"🛡 Админы (игровые ID): `{admins_list}`\n\n"
        f"**Игроки:**\n{players_preview}"
    )
    await safe_edit_or_send(callback, text, admin_keyboard(uid))
    await callback.answer()


@dp.callback_query(F.data == "adm_give_coins")
async def on_adm_give_coins(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_give_coins)
    await callback.message.answer(
        "💰 Отправь одним сообщением: `ИГРОВОЙ_ID СУММА`\nПример: `1001 500`",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(AdminStates.waiting_give_coins)
async def process_give_coins(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Формат: `ИГРОВОЙ_ID СУММА`.", parse_mode="Markdown")
        return
    try:
        gid = int(parts[0])
        amount = int(parts[1])
    except ValueError:
        await message.answer("⚠️ Игровой ID и сумма должны быть целыми числами.", parse_mode="Markdown")
        return

    target = get_user_by_game_id(gid)
    if not target:
        await message.answer(f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown")
        return

    target["coins"] += amount
    await state.clear()
    await message.answer(
        f"✅ Игроку `{gid}` (**{target['name']}**) изменено монет на **{amount:+d}**. Баланс: **{target['coins']}**.",
        reply_markup=admin_keyboard(message.from_user.id),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "adm_give_hp")
async def on_adm_give_hp(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_give_hp)
    await callback.message.answer(
        "❤️ Отправь одним сообщением: `ИГРОВОЙ_ID HP`\nПример: `1001 30`",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(AdminStates.waiting_give_hp)
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
        await message.answer("⚠️ Игровой ID и HP должны быть целыми числами.", parse_mode="Markdown")
        return

    target = get_user_by_game_id(gid)
    if not target:
        await message.answer(f"⚠️ Игрок с игровым ID `{gid}` не найден.", parse_mode="Markdown")
        return

    target["hp"] = max(0, min(MAX_HP, target["hp"] + amount))
    await state.clear()
    await message.answer(
        f"✅ Игроку `{gid}` (**{target['name']}**) изменено HP на **{amount:+d}**. Текущее HP: **{target['hp']}/{MAX_HP}**.",
        reply_markup=admin_keyboard(message.from_user.id),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "adm_set_id")
async def on_adm_set_id(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_set_game_id)
    await callback.message.answer(
        "🆔 Отправь одним сообщением: `СТАРЫЙ_ИГРОВОЙ_ID НОВЫЙ_ИГРОВОЙ_ID`\nПример: `1001 777`",
        parse_mode="Markdown",
    )
    await callback.answer()


@dp.message(AdminStates.waiting_set_game_id)
async def process_set_game_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Формат: `СТАРЫЙ_ИГРОВОЙ_ID НОВЫЙ_ИГРОВОЙ_ID`.", parse_mode="Markdown")
        return
    try:
        old_gid = int(parts[0])
        new_gid = int(parts[1])
    except ValueError:
        await message.answer("⚠️ Оба ID должны быть целыми числами.", parse_mode="Markdown")
        return

    target = get_user_by_game_id(old_gid)
    if not target:
        await message.answer(f"⚠️ Игрок с ID `{old_gid}` не найден.", parse_mode="Markdown")
        return
    if new_gid in game_to_tg:
        await message.answer(f"⚠️ Игровой ID `{new_gid}` уже занят другим игроком.", parse_mode="Markdown")
        return

    was_admin = old_gid in admins
    del game_to_tg[old_gid]
    target["game_id"] = new_gid
    game_to_tg[new_gid] = target["tg_id"]

    if was_admin:
        admins.discard(old_gid)
        admins.add(new_gid)

    await state.clear()
    await message.answer(
        f"✅ Игровой ID для **{target['name']}** изменён: `{old_gid}` → **`{new_gid}`**.",
        reply_markup=admin_keyboard(message.from_user.id),
        parse_mode="Markdown",
    )


@dp.callback_query(F.data == "adm_add_admin")
async def on_adm_add_admin(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("Только главный владелец", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_add_admin)
    await callback.message.answer("➕ Введи **игровой ID** игрока, которому выдать админку (например `1002`):", parse_mode="Markdown")
    await callback.answer()


@dp.message(AdminStates.waiting_add_admin)
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
        await message.answer(f"⚠️ Игрок с игровым ID `{gid}` не найден. Пусть сначала нажмёт /start.", parse_mode="Markdown")
        return

    admins.add(gid)
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
    await state.set_state(AdminStates.waiting_remove_admin)
    await callback.message.answer("➖ Введи **игровой ID**, у которого снять админку:", parse_mode="Markdown")
    await callback.answer()


@dp.message(AdminStates.waiting_remove_admin)
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
