import asyncio
import html
import time
import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import (
    ADMIN_MAX_RANK,
    ADMIN_TITLES,
    BOT_TOKEN,
    DB_PATH,
    FACTIONS,
    FACTION_RANKS,
    NICK_RE,
    WORK_COOLDOWN,
)
from database import (
    add_exp_and_money,
    bank_action,
    do_work,
    eat_food,
    get_player,
    get_player_by_game_id,
    get_top_players,
    heal_player,
    init_db,
    is_creator,
    play_casino,
    register_player,
    transfer_money,
)
from keyboards import admin_panel_kb, factions_kb, main_menu_kb


class RegState(StatesGroup):
    waiting_nick = State()


def esc(val) -> str:
    return html.escape(str(val if val is not None else ""), quote=False)


def has_admin(player: dict | None, min_lvl: int = 1) -> bool:
    if not player:
        return False
    if is_creator(int(player["tg_id"])):
        return True
    return int(player.get("admin_lvl", 0)) >= min_lvl


def admin_label(player: dict) -> str:
    if is_creator(int(player["tg_id"])):
        return "Создатель проекта (10 ур.)"
    lvl = int(player.get("admin_lvl", 0))
    if lvl <= 0:
        return "Игрок"
    return f"{ADMIN_TITLES.get(lvl, 'Администратор')} ({lvl} ур.)"


class BanCheckMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        tg_user = getattr(event, "from_user", None)
        if tg_user and not is_creator(tg_user.id):
            p = await get_player(tg_user.id)
            if p and int(p.get("banned", 0)) == 1:
                reason = p.get("ban_reason") or "Нарушение правил сервера"
                text = f"🚫 Ваш аккаунт заблокирован.\nПричина: <b>{esc(reason)}</b>"
                if isinstance(event, Message):
                    await event.answer(text, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer(f"Аккаунт заблокирован: {reason}", show_alert=True)
                return
        return await handler(event, data)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Укажите BOT_TOKEN в файле .env")

    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())

    # --- Регистрация и старт ---
    @dp.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext) -> None:
        uid = message.from_user.id
        p = await get_player(uid)

        if not p or not p.get("registered"):
            await state.set_state(RegState.waiting_nick)
            await message.answer(
                "🇷🇺 <b>Добро пожаловать на сервер CRMP!</b>\n"
                "Для регистрации введите RP-ник в формате <code>Имя_Фамилия</code>.\n"
                "Например: <code>Иван_Волков</code>",
                parse_mode="HTML",
            )
            return

        await state.clear()
        await message.answer(
            f"С возвращением, <b>{esc(p['nickname'])}</b> (<code>#{p['game_id']}</code>)!\n"
            f"💵 Наличные: <b>{p['cash']} ₽</b> | 🏦 Банк: <b>{p['bank']} ₽</b> | ⭐ Уровень: <b>{p['level']}</b>",
            reply_markup=main_menu_kb(has_admin(p, 1)),
            parse_mode="HTML",
        )

    @dp.message(RegState.waiting_nick)
    async def process_nick(message: Message, state: FSMContext) -> None:
        uid = message.from_user.id
        nick = (message.text or "").strip()

        if not NICK_RE.match(nick):
            await message.answer(
                "⚠️ Неверный формат ника. Используйте <code>Имя_Фамилия</code> (без пробелов, от 5 до 31 символа).",
                parse_mode="HTML",
            )
            return

        ok, err, player = await register_player(uid, nick)
        if not ok or not player:
            await message.answer(f"❌ {err}", parse_mode="HTML")
            return

        await state.clear()
        role_note = "\n👑 Вам автоматически выданы права <b>Создателя (10 ур.)</b>!" if is_creator(uid) else ""
        await message.answer(
            f"✅ Регистрация завершена!\n"
            f"• Ник: <b>{esc(player['nickname'])}</b>\n"
            f"• Игровой ID: <code>#{player['game_id']}</code>\n"
            f"• Стартовый капитал: <b>{player['cash']} ₽</b>{role_note}",
            reply_markup=main_menu_kb(has_admin(player, 1)),
            parse_mode="HTML",
        )

    # --- Профиль и экономика ---
    @dp.message(F.text == "👤 Профиль")
    @dp.message(Command("profile"))
    async def cmd_profile(message: Message) -> None:
        p = await get_player(message.from_user.id)
        if not p or not p.get("registered"):
            await message.answer("Напишите /start для регистрации.")
            return

        need_xp = int(p["level"]) * 100
        fac_key = p.get("faction", "none")
        if fac_key in FACTIONS:
            rk = int(p.get("rank", 1))
            fac_line = f"<b>{esc(FACTIONS[fac_key]['name'])}</b> — {esc(FACTION_RANKS.get(rk, f'{rk} ранг'))} (<code>{rk}/11</code>)"
        else:
            fac_line = "<b>Гражданский</b>"

        adm_line = f"\n🛡 Статус: <b>{esc(admin_label(p))}</b>" if has_admin(p, 1) else ""
        wanted_line = f"\n🚨 Розыск: <b><code>{p['wanted']}/6</code></b>" if int(p.get("wanted", 0)) > 0 else ""

        await message.answer(
            f"👤 <b>Паспорт игрока: {esc(p['nickname'])}</b> (<code>#{p['game_id']}</code>)\n"
            f"• Уровень: <b>{p['level']}</b> (<code>{p['exp']}/{need_xp} XP</code>)\n"
            f"• Наличные: <b>{p['cash']} ₽</b> | Банк: <b>{p['bank']} ₽</b>\n"
            f"• Фракция: {fac_line}\n"
            f"• ❤️ Здоровье: <code>{p['hp']}/100</code> | 🍗 Сытость: <code>{p['hunger']}/100</code>"
            f"{wanted_line}{adm_line}",
            reply_markup=main_menu_kb(has_admin(p, 1)),
            parse_mode="HTML",
        )

    @dp.message(F.text == "💼 Работа")
    @dp.message(Command("work"))
    async def cmd_work(message: Message) -> None:
        ok, text = await do_work(message.from_user.id, WORK_COOLDOWN)
        await message.answer(text, parse_mode="HTML")

    @dp.message(F.text == "🍔 Еда")
    @dp.message(Command("eat"))
    async def cmd_eat(message: Message) -> None:
        _, text = await eat_food(message.from_user.id)
        await message.answer(text, parse_mode="HTML")

    @dp.message(F.text == "🏥 Больница")
    @dp.message(Command("heal"))
    async def cmd_heal(message: Message) -> None:
        _, text = await heal_player(message.from_user.id)
        await message.answer(text, parse_mode="HTML")

    @dp.message(F.text == "🎰 Казино")
    @dp.message(Command("casino"))
    async def cmd_casino(message: Message) -> None:
        parts = (message.text or "").split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("🎰 Использование: <code>/casino &lt;сумма&gt;</code> (например, <code>/casino 5000</code>)", parse_mode="HTML")
            return
        _, text = await play_casino(message.from_user.id, int(parts[1]))
        await message.answer(text, parse_mode="HTML")

    @dp.message(Command("bank"))
    async def cmd_bank(message: Message) -> None:
        parts = (message.text or "").split()
        if len(parts) != 3 or parts[1].lower() not in {"put", "take"} or not parts[2].isdigit():
            await message.answer("🏦 Использование: <code>/bank put &lt;сумма&gt;</code> или <code>/bank take &lt;сумма&gt;</code>", parse_mode="HTML")
            return
        _, text = await bank_action(message.from_user.id, parts[1].lower(), int(parts[2]))
        await message.answer(text, parse_mode="HTML")

    @dp.message(Command("pay"))
    async def cmd_pay(message: Message) -> None:
        parts = (message.text or "").split()
        if len(parts) != 3 or not parts[1].lstrip("#").isdigit() or not parts[2].isdigit():
            await message.answer("💸 Использование: <code>/pay &lt;ID&gt; &lt;сумма&gt;</code>", parse_mode="HTML")
            return
        ok, text, target_tg, notify = await transfer_money(
            message.from_user.id, int(parts[1].lstrip("#")), int(parts[2])
        )
        await message.answer(text, parse_mode="HTML")
        if ok and target_tg:
            try:
                await bot.send_message(target_tg, notify, parse_mode="HTML")
            except Exception:
                pass

    @dp.message(F.text == "🏆 Топ")
    @dp.message(Command("top"))
    async def cmd_top(message: Message) -> None:
        rows = await get_top_players(10)
        if not rows:
            await message.answer("🏆 Рейтинг пока пуст.")
            return
        lines = ["🏆 <b>Топ-10 богачей области:</b>\n"]
        for i, r in enumerate(rows, start=1):
            lines.append(f"{i}. <b>{esc(r['nickname'])}</b> (<code>#{r['game_id']}</code>) — <b>{r['total']} ₽</b> (ур. {r['level']})")
        await message.answer("\n".join(lines), parse_mode="HTML")

    # --- Фракции ---
    @dp.message(F.text == "🏛 Фракции")
    @dp.message(Command("factions"))
    async def cmd_factions(message: Message) -> None:
        p = await get_player(message.from_user.id)
        if not p or not p.get("registered"):
            await message.answer("Напишите /start для регистрации.")
            return

        fac = p.get("faction", "none")
        if fac in FACTIONS:
            rk = int(p.get("rank", 1))
            await message.answer(
                f"🏛 <b>Ваша фракция: {esc(FACTIONS[fac]['name'])}</b>\n"
                f"• Должность/ранг: <b>{esc(FACTION_RANKS.get(rk, f'{rk} ранг'))}</b> (<code>{rk}/11</code>)\n"
                f"• Выговоров: <code>{p.get('f_warns', 0)}/3</code>\n"
                f"• Рация фракции: <code>/r &lt;текст&gt;</code>",
                parse_mode="HTML",
            )
            return

        await message.answer(
            "🏛 <b>Фракции сервера</b>\nНажмите на организацию, чтобы подать заявку на вступление:",
            reply_markup=factions_kb(),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("fac_apply:"))
    async def cb_fac_apply(callback: CallbackQuery) -> None:
        uid = callback.from_user.id
        fid = callback.data.split(":", 1)[1]
        p = await get_player(uid)
        if not p or not p.get("registered"):
            await callback.answer("Сначала пройдите регистрацию через /start", show_alert=True)
            return
        if p.get("faction", "none") != "none":
            await callback.answer("Вы уже состоите во фракции", show_alert=True)
            return
        info = FACTIONS.get(fid)
        if not info:
            await callback.answer("Фракция не найдена", show_alert=True)
            return
        if int(p["level"]) < int(info["min_lvl"]):
            await callback.answer(f"Нужен минимум {info['min_lvl']} уровень", show_alert=True)
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO faction_apps (tg_id, faction, status, created_at)
                VALUES (?, ?, 'pending', ?)
                ON CONFLICT(tg_id, faction) DO UPDATE SET status = 'pending', created_at = excluded.created_at
                """,
                (uid, fid, int(time.time())),
            )
            await db.commit()

        await callback.answer("Заявка подана!", show_alert=True)
        if callback.message:
            await callback.message.answer(
                f"📩 Заявка в <b>{esc(info['name'])}</b> отправлена.\n"
                f"Лидер или админ может принять её командой <code>/faccept {p['game_id']}</code>.",
                parse_mode="HTML",
            )

    @dp.message(Command("r"))
    async def cmd_f_radio(message: Message) -> None:
        p = await get_player(message.from_user.id)
        fid = p.get("faction", "none") if p else "none"
        if fid not in FACTIONS:
            await message.answer("⛔ Вы не состоите во фракции.")
            return
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await message.answer("Формат: <code>/r &lt;сообщение&gt;</code>", parse_mode="HTML")
            return

        rk = int(p.get("rank", 1))
        out = f"📻 <b>[{esc(FACTIONS[fid]['name'])}] {esc(p['nickname'])}:</b> {esc(parts[1].strip())}"
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT tg_id FROM players WHERE faction = ?", (fid,))
            rows = await cur.fetchall()

        sent = 0
        for (member_tg,) in rows:
            try:
                await bot.send_message(int(member_tg), out, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        await message.answer(f"✅ Сообщение отправлено <code>{sent}</code> участникам фракции.", parse_mode="HTML")

    @dp.message(Command("fapps"))
    async def cmd_fapps(message: Message) -> None:
        p = await get_player(message.from_user.id)
        fid = p.get("leader_of") if p else None
        if not fid and has_admin(p, 7):
            parts = (message.text or "").split()
            fid = parts[1].lower() if len(parts) > 1 and parts[1].lower() in FACTIONS else None
        if not fid or fid not in FACTIONS:
            await message.answer("⛔ Доступно лидерам фракций и админам 7+ ур. (<code>/fapps [фракция]</code>).", parse_mode="HTML")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT pl.game_id, pl.nickname, pl.level
                FROM faction_apps fa
                JOIN players pl ON pl.tg_id = fa.tg_id
                WHERE fa.faction = ? AND fa.status = 'pending'
                """,
                (fid,),
            )
            apps = await cur.fetchall()

        if not apps:
            await message.answer(f"Заявок в <b>{esc(FACTIONS[fid]['name'])}</b> нет.", parse_mode="HTML")
            return

        lines = [f"📩 <b>Заявки в {esc(FACTIONS[fid]['name'])}:</b>\n"]
        for a in apps:
            lines.append(f"• <b>{esc(a['nickname'])}</b> (<code>#{a['game_id']}</code>, ур. {a['level']}) — <code>/faccept {a['game_id']}</code>")
        await message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("faccept"))
    async def cmd_faccept(message: Message) -> None:
        p = await get_player(message.from_user.id)
        parts = (message.text or "").split()
        if len(parts) != 2 or not parts[1].lstrip("#").isdigit():
            await message.answer("Формат: <code>/faccept &lt;игровой_ID&gt;</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT faction FROM faction_apps WHERE tg_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1",
                (target["tg_id"],),
            )
            app = await cur.fetchone()
            fid = p.get("leader_of") if p else None
            if not fid:
                if has_admin(p, 7) and app:
                    fid = app["faction"]
                else:
                    await message.answer("⛔ Нет прав для принятия во фракцию.")
                    return

            await db.execute(
                "UPDATE players SET faction = ?, rank = 1, f_warns = 0 WHERE tg_id = ?",
                (fid, target["tg_id"]),
            )
            await db.execute(
                "UPDATE faction_apps SET status = 'accepted' WHERE tg_id = ? AND faction = ?",
                (target["tg_id"], fid),
            )
            await db.commit()

        await message.answer(f"✅ <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) принят в <b>{esc(FACTIONS[fid]['name'])}</b>!", parse_mode="HTML")
        try:
            await bot.send_message(int(target["tg_id"]), f"🎉 Вас приняли в <b>{esc(FACTIONS[fid]['name'])}</b>!", parse_mode="HTML")
        except Exception:
            pass

    @dp.message(Command("fwarn"))
    async def cmd_fwarn(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2 or not parts[1].lstrip("#").isdigit():
            await message.answer("Формат: <code>/fwarn &lt;ID&gt; [причина]</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        target = await get_player_by_game_id(gid)
        if not target or target.get("faction", "none") == "none":
            await message.answer("Игрок не найден или не состоит во фракции.")
            return
        tfid = target["faction"]
        if (actor or {}).get("leader_of") != tfid and not has_admin(actor, 7):
            await message.answer("⛔ Выдавать выговоры может лидер этой фракции или админ 7+ ур.")
            return

        reason = parts[2].strip() if len(parts) == 3 else "Нарушение устава"
        warns = int(target.get("f_warns", 0)) + 1

        async with aiosqlite.connect(DB_PATH) as db:
            if warns >= 3:
                await db.execute(
                    "UPDATE players SET faction = 'none', rank = 0, f_warns = 0, leader_of = NULL WHERE tg_id = ?",
                    (target["tg_id"],),
                )
                await db.commit()
                await message.answer(f"⛔ <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) получил 3/3 выговоров и уволен!", parse_mode="HTML")
            else:
                await db.execute("UPDATE players SET f_warns = ? WHERE tg_id = ?", (warns, target["tg_id"]))
                await db.commit()
                await message.answer(f"⚠️ Выдан выговор <b>{esc(target['nickname'])}</b> (<code>{warns}/3</code>). Причина: <i>{esc(reason)}</i>.", parse_mode="HTML")

    # --- Промокоды ---
    @dp.message(Command("promo"))
    async def cmd_promo(message: Message) -> None:
        p = await get_player(message.from_user.id)
        if not p or not p.get("registered"):
            await message.answer("Сначала напишите /start.")
            return
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.answer("Формат: <code>/promo &lt;КОД&gt;</code>", parse_mode="HTML")
            return
        code = parts[1].strip().upper()

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur_p = await db.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
                promo = await cur_p.fetchone()
                if not promo or int(promo["uses_left"]) <= 0:
                    await db.rollback()
                    await message.answer("❌ Промокод не найден или закончился.")
                    return

                cur_u = await db.execute("SELECT 1 FROM promo_uses WHERE code = ? AND tg_id = ?", (code, p["tg_id"]))
                if await cur_u.fetchone():
                    await db.rollback()
                    await message.answer("⚠️ Вы уже активировали этот промокод.")
                    return

                await db.execute(
                    "INSERT INTO promo_uses (code, tg_id) VALUES (?, ?)",
                    (code, p["tg_id"]),
                )
                await db.execute(
                    "UPDATE promocodes SET uses_left = uses_left - 1 WHERE code = ?",
                    (code,),
                )
                await add_exp_and_money(
                    db,
                    int(p["tg_id"]),
                    int(promo["money"]),
                    int(promo["exp"]),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise

        await message.answer(
            f"🎉 Промокод <code>{esc(code)}</code> активирован! Получено <b>+{promo['money']} ₽</b> и <b>+{promo['exp']} XP</b>.",
            parse_mode="HTML",
        )

    # --- Админка ---
    @dp.message(F.text == "🛡 Админка")
    @dp.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        p = await get_player(message.from_user.id)
        if not has_admin(p, 1):
            await message.answer("⛔ Нет доступа к админ-панели.")
            return
        await message.answer(
            f"🛡 <b>Админ-панель</b>\n"
            f"Ваш статус: <b>{esc(admin_label(p))}</b>\n\n"
            f"• <code>/givemoney &lt;ID&gt; &lt;сумма&gt;</code> — выдать наличные\n"
            f"• <code>/setlvl &lt;ID&gt; &lt;уровень&gt;</code> — установить уровень\n"
            f"• <code>/setleader &lt;ID&gt; &lt;фракция|none&gt;</code> — назначить лидера\n"
            f"• <code>/setadmin &lt;ID&gt; &lt;0..10&gt;</code> — выдать админку\n"
            f"• <code>/addpromo &lt;КОД&gt; &lt;деньги&gt; &lt;xp&gt; &lt;активаций&gt;</code> — создать промокод\n"
            f"• <code>/ban &lt;ID&gt; [причина]</code> / <code>/unban &lt;ID&gt;</code> — бан / разбан\n"
            f"• <code>/resetplayer &lt;ID&gt;</code> — сбросить прогресс игрока",
            reply_markup=admin_panel_kb(),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data == "adm_players")
    async def cb_adm_players(callback: CallbackQuery) -> None:
        p = await get_player(callback.from_user.id)
        if not has_admin(p, 1):
            await callback.answer("Недостаточно прав", show_alert=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT game_id, nickname, level, cash, bank, admin_lvl, banned FROM players ORDER BY game_id ASC LIMIT 25"
            )
            rows = await cur.fetchall()
        lines = ["👥 <b>Игроки:</b>\n"]
        for r in rows:
            b_tag = " 🚫" if r["banned"] else ""
            a_tag = f" [Адм {r['admin_lvl']}]" if r["admin_lvl"] else ""
            lines.append(
                f"• <code>#{r['game_id']}</code> <b>{esc(r['nickname'])}</b> — {r['level']} ур. | {r['cash'] + r['bank']} ₽{a_tag}{b_tag}"
            )
        await callback.answer()
        if callback.message:
            await callback.message.answer("\n".join(lines), parse_mode="HTML")

    @dp.callback_query(F.data == "adm_promos")
    async def cb_adm_promos(callback: CallbackQuery) -> None:
        p = await get_player(callback.from_user.id)
        if not has_admin(p, 1):
            await callback.answer("Недостаточно прав", show_alert=True)
            return
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT code, money, exp, uses_left FROM promocodes")
            rows = await cur.fetchall()
        if not rows:
            await callback.answer("Промокодов нет", show_alert=True)
            return
        lines = ["🎟 <b>Промокоды:</b>\n"] + [
            f"• <code>{esc(r['code'])}</code>: +{r['money']} ₽, +{r['exp']} XP (осталось: {r['uses_left']})" for r in rows
        ]
        await callback.answer()
        if callback.message:
            await callback.message.answer("\n".join(lines), parse_mode="HTML")

    @dp.message(Command("givemoney"))
    async def cmd_givemoney(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 6):
            await message.answer("⛔ Доступно с 6 ранга администратора.")
            return
        parts = (message.text or "").split()
        if len(parts) != 3 or not parts[1].lstrip("#").isdigit() or not parts[2].lstrip("-").isdigit():
            await message.answer("Формат: <code>/givemoney &lt;ID&gt; &lt;сумма&gt;</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        amt = int(parts[2])
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE players SET cash = MAX(0, cash + ?) WHERE tg_id = ?", (amt, target["tg_id"]))
            await db.commit()
        await message.answer(
            f"💵 Игроку <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) изменены наличные на <b>{amt} ₽</b>.",
            parse_mode="HTML",
        )

    @dp.message(Command("setlvl"))
    async def cmd_setlvl(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 6):
            await message.answer("⛔ Доступно с 6 ранга администратора.")
            return
        parts = (message.text or "").split()
        if len(parts) != 3 or not parts[1].lstrip("#").isdigit() or not parts[2].isdigit():
            await message.answer("Формат: <code>/setlvl &lt;ID&gt; &lt;уровень&gt;</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        lvl = max(1, min(100, int(parts[2])))
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE players SET level = ?, exp = 0 WHERE tg_id = ?", (lvl, target["tg_id"]))
            await db.commit()
        await message.answer(
            f"⭐ Игроку <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) установлен <b>{lvl} уровень</b>.",
            parse_mode="HTML",
        )

    @dp.message(Command("setleader"))
    async def cmd_setleader(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 7):
            await message.answer("⛔ Доступно с 7 ранга администратора.")
            return
        parts = (message.text or "").split()
        if len(parts) != 3 or not parts[1].lstrip("#").isdigit():
            keys = ", ".join(f"<code>{k}</code>" for k in FACTIONS)
            await message.answer(f"Формат: <code>/setleader &lt;ID&gt; &lt;фракция|none&gt;</code>\nФракции: {keys}", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        fid = parts[2].strip().lower()
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            if fid == "none":
                await db.execute("UPDATE players SET leader_of = NULL WHERE tg_id = ?", (target["tg_id"],))
                await db.commit()
                await message.answer(f"✅ <b>{esc(target['nickname'])}</b> снят с лидерки.", parse_mode="HTML")
                return
            if fid not in FACTIONS:
                await message.answer("Неизвестный ключ фракции.")
                return
            await db.execute(
                "UPDATE players SET faction = ?, rank = 11, leader_of = ?, f_warns = 0 WHERE tg_id = ?",
                (fid, fid, target["tg_id"]),
            )
            await db.commit()

        await message.answer(
            f"👑 <b>{esc(target['nickname'])}</b> назначен лидером <b>{esc(FACTIONS[fid]['name'])}</b>!",
            parse_mode="HTML",
        )

    @dp.message(Command("setadmin"))
    async def cmd_setadmin(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        actor_lvl = 10 if is_creator(message.from_user.id) else int((actor or {}).get("admin_lvl", 0))
        if actor_lvl < 9:
            await message.answer("⛔ Назначать администраторов можно с 9 ранга или создателю.")
            return
        parts = (message.text or "").split()
        if len(parts) != 3 or not parts[1].lstrip("#").isdigit() or not parts[2].isdigit():
            await message.answer(f"Формат: <code>/setadmin &lt;ID&gt; &lt;0..{ADMIN_MAX_RANK}&gt;</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        lvl = int(parts[2])
        if not (0 <= lvl <= ADMIN_MAX_RANK):
            await message.answer(f"Уровень должен быть от 0 до {ADMIN_MAX_RANK}.")
            return
        if not is_creator(message.from_user.id) and lvl >= actor_lvl:
            await message.answer("⛔ Нельзя выдать ранг равный или выше своего.")
            return

        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return
        if is_creator(int(target["tg_id"])):
            await message.answer("⛔ Нельзя менять права создателя.")
            return

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE players SET admin_lvl = ? WHERE tg_id = ?", (lvl, target["tg_id"]))
            await db.commit()

        await message.answer(
            f"🛡 Игроку <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) выдан админ-ранг <b>{lvl}</b>.",
            parse_mode="HTML",
        )

    @dp.message(Command("addpromo"))
    async def cmd_addpromo(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 6):
            await message.answer("⛔ Доступно с 6 ранга администратора.")
            return
        parts = (message.text or "").split()
        if len(parts) != 5 or not all(x.isdigit() for x in parts[2:]):
            await message.answer("Формат: <code>/addpromo &lt;КОД&gt; &lt;деньги&gt; &lt;xp&gt; &lt;активаций&gt;</code>", parse_mode="HTML")
            return
        code = parts[1].strip().upper()
        money_val, exp_val, uses_val = int(parts[2]), int(parts[3]), int(parts[4])
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO promocodes (code, money, exp, uses_left)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    money = excluded.money,
                    exp = excluded.exp,
                    uses_left = excluded.uses_left
                """,
                (code, money_val, exp_val, uses_val),
            )
            await db.commit()
        await message.answer(
            f"🎟 Промокод <code>{esc(code)}</code> сохранён (+{money_val} ₽, +{exp_val} XP, активаций: {uses_val}).",
            parse_mode="HTML",
        )

    @dp.message(Command("ban"))
    async def cmd_ban(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 4):
            await message.answer("⛔ Доступно с 4 ранга администратора.")
            return
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2 or not parts[1].lstrip("#").isdigit():
            await message.answer("Формат: <code>/ban &lt;ID&gt; [причина]</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        reason = parts[2].strip() if len(parts) == 3 else "Нарушение правил сервера"
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return
        if is_creator(int(target["tg_id"])):
            await message.answer("⛔ Нельзя заблокировать создателя.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE players SET banned = 1, ban_reason = ? WHERE tg_id = ?", (reason, target["tg_id"]))
            await db.commit()
        await message.answer(
            f"🚫 Игрок <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) заблокирован.",
            parse_mode="HTML",
        )

    @dp.message(Command("unban"))
    async def cmd_unban(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 4):
            await message.answer("⛔ Доступно с 4 ранга администратора.")
            return
        parts = (message.text or "").split()
        if len(parts) != 2 or not parts[1].lstrip("#").isdigit():
            await message.answer("Формат: <code>/unban &lt;ID&gt;</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE players SET banned = 0, ban_reason = '' WHERE tg_id = ?", (target["tg_id"],))
            await db.commit()
        await message.answer(
            f"✅ Игрок <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) разблокирован.",
            parse_mode="HTML",
        )

    @dp.message(Command("resetplayer"))
    async def cmd_resetplayer(message: Message) -> None:
        actor = await get_player(message.from_user.id)
        if not has_admin(actor, 9):
            await message.answer("⛔ Доступно с 9 ранга или создателю.")
            return
        parts = (message.text or "").split()
        if len(parts) != 2 or not parts[1].lstrip("#").isdigit():
            await message.answer("Формат: <code>/resetplayer &lt;ID&gt;</code>", parse_mode="HTML")
            return
        gid = int(parts[1].lstrip("#"))
        target = await get_player_by_game_id(gid)
        if not target:
            await message.answer("Игрок не найден.")
            return
        t_tg = int(target["tg_id"])
        keep_admin = 10 if is_creator(t_tg) else int(target.get("admin_lvl", 0))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                UPDATE players
                SET level = 1, exp = 0, cash = 5000, bank = 0, hp = 100, hunger = 100,
                    faction = 'none', rank = 0, f_warns = 0, leader_of = NULL,
                    wanted = 0, banned = 0, ban_reason = '', admin_lvl = ?
                WHERE tg_id = ?
                """,
                (keep_admin, t_tg),
            )
            await db.commit()
        await message.answer(
            f"♻️ Прогресс игрока <b>{esc(target['nickname'])}</b> (<code>#{gid}</code>) сброшен.",
            parse_mode="HTML",
        )

    # --- Справка ---
    @dp.message(F.text == "📖 Команды")
    @dp.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(
            "📖 <b>Команды сервера:</b>\n"
            "• <code>/start</code> — вход и регистрация ника\n"
            "• <code>/profile</code> — профиль и характеристики\n"
            "• <code>/work</code> — отработать смену\n"
            "• <code>/eat</code> — перекусить | <code>/heal</code> — лечение\n"
            "• <code>/bank put|take &lt;сумма&gt;</code> — банк\n"
            "• <code>/pay &lt;ID&gt; &lt;сумма&gt;</code> — перевод игроку\n"
            "• <code>/casino &lt;сумма&gt;</code> — ставка в казино\n"
            "• <code>/promo &lt;КОД&gt;</code> — активация промокода\n"
            "• <code>/factions</code>, <code>/r &lt;текст&gt;</code>, <code>/fapps</code>, <code>/faccept &lt;ID&gt;</code>, <code>/fwarn &lt;ID&gt;</code>\n"
            "• <code>/top</code> — топ-10 богачей",
            parse_mode="HTML",
        )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
