import random
import time
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()

BOSS_MAX_HP = 500
BOSS_COOLDOWN = 60  # секунд между атаками игрока
boss_hp = BOSS_MAX_HP
last_player_hit: dict[int, float] = {}


def boss_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Атаковать босса", callback_data="act_boss_hit")],
            [InlineKeyboardButton(text="🔄 Обновить статус босса", callback_data="act_boss")],
        ]
    )


def format_boss_status() -> str:
    bar_len = 10
    filled = max(0, min(bar_len, round((boss_hp / BOSS_MAX_HP) * bar_len)))
    bar = "🟥" * filled + "⬜" * (bar_len - filled)
    return (
        "🐉 **Рейд-босс: Тёмный Страж**\n\n"
        f"❤️ HP: **{max(0, boss_hp)}/{BOSS_MAX_HP}**\n"
        f"[{bar}]\n\n"
        "Бей босса вместе с другими игроками — за победу награда монетами и XP!"
    )


@router.message(Command("boss"))
async def cmd_boss(message: Message):
    await message.answer(format_boss_status(), reply_markup=boss_keyboard(), parse_mode="Markdown")


@router.callback_query(F.data == "act_boss")
async def on_boss_menu(callback: CallbackQuery):
    await callback.message.answer(format_boss_status(), reply_markup=boss_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "act_boss_hit")
async def on_boss_hit(callback: CallbackQuery):
    global boss_hp

    uid = callback.from_user.id
    now = time.time()
    rem = int(BOSS_COOLDOWN - (now - last_player_hit.get(uid, 0.0)))
    if rem > 0:
        await callback.answer(f"⏳ Перезарядка удара: ещё {rem} сек.", show_alert=True)
        return

    last_player_hit[uid] = now
    dmg = random.randint(25, 60)
    boss_hp = max(0, boss_hp - dmg)

    if boss_hp == 0:
        reward_coins = random.randint(120, 220)
        reward_xp = 40
        boss_hp = BOSS_MAX_HP  # возрождаем босса после победы
        await callback.message.answer(
            f"💥 Ты нанёс **{dmg}** урона и **добил босса**!\n"
            f"🏆 Твоя награда: **+{reward_coins}** монет и **+{reward_xp}** XP!\n"
            f"🐉 Новый босс уже вышел на арену.",
            reply_markup=boss_keyboard(),
            parse_mode="Markdown",
        )
    else:
        await callback.message.answer(
            f"⚔️ Ты нанёс боссу **{dmg}** урона!\n\n{format_boss_status()}",
            reply_markup=boss_keyboard(),
            parse_mode="Markdown",
        )

    await callback.answer(f"-{dmg} HP боссу")
