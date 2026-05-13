import asyncio
import logging
import sqlite3
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile
)

# ═══════════════════════════════════════════
#   НАСТРОЙКИ — заполни только это!
# ═══════════════════════════════════════════
import os
BOT_TOKEN = os.environ["8736226584:AAEmNywlassWpIpQEqCPDaxqDLTikREkoFI"]
ADMIN_ID   = int(os.environ["64775775"])

# ═══════════════════════════════════════════
#   КАТАЛОГ ПОДАРКОВ
#   Добавляй/убирай подарки здесь
# ═══════════════════════════════════════════
GIFTS = [
    {
        "id": "gift_6026193266406327981",
        "name": "🎁 Редкий подарок",
        "description": "Нелимитированный подарок, убранный из магазина Telegram. Отправка вручную после оплаты.",
        "price": 60,
        "emoji": "🎁",
        "available": True,
    },
    # Добавляй новые подарки по этому шаблону:
    # {
    #     "id": "gift_XXXXX",        # уникальный ID
    #     "name": "🎀 Название",
    #     "description": "Описание",
    #     "price": 100,              # цена в Stars
    #     "emoji": "🎀",
    #     "available": True,
    # },
]

# ═══════════════════════════════════════════

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ───────────────────────────────────────────
# База данных
# ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            payload     TEXT UNIQUE,
            user_id     INTEGER,
            username    TEXT,
            gift_id     TEXT,
            gift_name   TEXT,
            stars       INTEGER,
            status      TEXT DEFAULT 'paid',
            created_at  TEXT,
            delivered_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_order(payload, user_id, username, gift_id, gift_name, stars):
    conn = sqlite3.connect("orders.db")
    conn.execute("""
        INSERT OR IGNORE INTO orders
        (payload, user_id, username, gift_id, gift_name, stars, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'paid', ?)
    """, (payload, user_id, username, gift_id, gift_name, stars,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def mark_delivered(payload):
    conn = sqlite3.connect("orders.db")
    conn.execute("""
        UPDATE orders SET status='delivered', delivered_at=?
        WHERE payload=?
    """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), payload))
    conn.commit()
    conn.close()

def get_pending_orders():
    conn = sqlite3.connect("orders.db")
    rows = conn.execute("""
        SELECT payload, user_id, username, gift_name, stars, created_at
        FROM orders WHERE status='paid'
        ORDER BY created_at
    """).fetchall()
    conn.close()
    return rows

def get_order(payload):
    conn = sqlite3.connect("orders.db")
    row = conn.execute("SELECT * FROM orders WHERE payload=?", (payload,)).fetchone()
    conn.close()
    return row

def get_all_orders():
    conn = sqlite3.connect("orders.db")
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return rows

# ───────────────────────────────────────────
# Хелперы
# ───────────────────────────────────────────
def get_gift(gift_id):
    return next((g for g in GIFTS if g["id"] == gift_id), None)

def catalog_keyboard():
    buttons = []
    for g in GIFTS:
        if g["available"]:
            buttons.append([InlineKeyboardButton(
                text=f"{g['emoji']} {g['name']} — {g['price']}⭐",
                callback_data=f"info:{g['id']}"
            )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def gift_keyboard(gift_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💫 Купить", callback_data=f"buy:{gift_id}"),
        InlineKeyboardButton(text="◀️ Назад",  callback_data="catalog"),
    ]])

# ───────────────────────────────────────────
# /start
# ───────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет!\n\n"
        "Здесь можно купить *редкие подарки Telegram*, "
        "которые уже убраны из магазина.\n\n"
        "📦 Доставка — вручную после оплаты (обычно до 10 минут).\n"
        "💬 Вопросы — пиши сюда, ответим.\n\n"
        "👇 Смотри каталог:",
        parse_mode="Markdown",
        reply_markup=catalog_keyboard()
    )

# ───────────────────────────────────────────
# Каталог
# ───────────────────────────────────────────
@dp.message(Command("catalog"))
async def cmd_catalog(message: types.Message):
    await message.answer(
        "🛍 *Каталог подарков*\n\nВыбери подарок:",
        parse_mode="Markdown",
        reply_markup=catalog_keyboard()
    )

@dp.callback_query(F.data == "catalog")
async def cb_catalog(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🛍 *Каталог подарков*\n\nВыбери подарок:",
        parse_mode="Markdown",
        reply_markup=catalog_keyboard()
    )
    await callback.answer()

# ───────────────────────────────────────────
# Инфо о подарке
# ───────────────────────────────────────────
@dp.callback_query(F.data.startswith("info:"))
async def cb_gift_info(callback: types.CallbackQuery):
    gift_id = callback.data.split(":")[1]
    gift = get_gift(gift_id)
    if not gift:
        await callback.answer("Подарок не найден", show_alert=True)
        return

    text = (
        f"{gift['emoji']} *{gift['name']}*\n\n"
        f"📝 {gift['description']}\n\n"
        f"💰 Цена: *{gift['price']} Stars*\n"
        f"🚚 Доставка: вручную (до 10 минут)\n\n"
        f"После оплаты ты получишь уведомление когда подарок будет отправлен."
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=gift_keyboard(gift_id)
    )
    await callback.answer()

# ───────────────────────────────────────────
# Создание инвойса
# ───────────────────────────────────────────
@dp.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: types.CallbackQuery):
    gift_id = callback.data.split(":")[1]
    gift = get_gift(gift_id)
    if not gift:
        await callback.answer("Подарок не найден", show_alert=True)
        return

    user_id = callback.from_user.id
    payload = f"{gift_id}_{user_id}_{int(datetime.now().timestamp())}"

    await bot.send_invoice(
        chat_id=user_id,
        title=f"{gift['emoji']} {gift['name']}",
        description=gift["description"],
        payload=payload,
        currency="XTR",          # Telegram Stars
        prices=[LabeledPrice(label=gift["name"], amount=gift["price"])],
        provider_token="",        # пусто для Stars
        photo_url=None,
        is_flexible=False,
    )
    await callback.answer("💫 Счёт отправлен!")

# ───────────────────────────────────────────
# Подтверждение перед оплатой
# ───────────────────────────────────────────
@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

# ───────────────────────────────────────────
# Успешная оплата
# ───────────────────────────────────────────
@dp.message(F.successful_payment)
async def payment_success(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else str(user_id)

    # Определяем что купили
    gift_id = payload.split("_")[0] + "_" + payload.split("_")[1]  # gift_N
    gift = get_gift(gift_id)
    gift_name = gift["name"] if gift else payload
    stars = payment.total_amount

    # Сохраняем в БД
    save_order(payload, user_id, username, gift_id, gift_name, stars)

    # Сообщаем пользователю
    await message.answer(
        f"✅ *Оплата прошла!*\n\n"
        f"Подарок: {gift_name}\n"
        f"Оплачено: {stars} ⭐\n\n"
        f"⏳ Отправим в течение 10 минут.\n"
        f"Ты получишь уведомление как только подарок будет у тебя!",
        parse_mode="Markdown"
    )

    # ─── Уведомление админу ───
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправил подарок", callback_data=f"done:{payload}"),
            InlineKeyboardButton(text="❌ Проблема",         callback_data=f"problem:{payload}"),
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"🛎 *Новый заказ!*\n\n"
        f"👤 Пользователь: {username} (`{user_id}`)\n"
        f"🎁 Подарок: {gift_name}\n"
        f"💰 Stars: {stars}\n"
        f"📦 Payload: `{payload}`\n\n"
        f"👆 После того как отправишь подарок вручную — нажми кнопку:",
        parse_mode="Markdown",
        reply_markup=admin_kb
    )

# ───────────────────────────────────────────
# Админ: подтверждение доставки
# ───────────────────────────────────────────
@dp.callback_query(F.data.startswith("done:"))
async def cb_done(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return

    payload = callback.data[5:]
    order = get_order(payload)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    mark_delivered(payload)

    user_id = order[2]
    gift_name = order[5]

    # Уведомляем покупателя
    await bot.send_message(
        user_id,
        f"🎁 *Подарок отправлен!*\n\n"
        f"{gift_name} уже летит к тебе.\n"
        f"Проверь входящие сообщения в Telegram!\n\n"
        f"Спасибо за покупку 💫",
        parse_mode="Markdown"
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ *ДОСТАВЛЕНО*",
        parse_mode="Markdown"
    )
    await callback.answer("✅ Отмечено как доставленное!")

# ───────────────────────────────────────────
# Админ: проблема с заказом
# ───────────────────────────────────────────
@dp.callback_query(F.data.startswith("problem:"))
async def cb_problem(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Нет доступа", show_alert=True)
        return

    payload = callback.data[8:]
    order = get_order(payload)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    user_id = order[2]

    await bot.send_message(
        user_id,
        f"⚠️ Возникла небольшая проблема с твоим заказом.\n"
        f"Администратор свяжется с тобой в ближайшее время для решения.",
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n⚠️ *ПРОБЛЕМА — связались с юзером*",
        parse_mode="Markdown"
    )
    await callback.answer("Пользователь уведомлён")

# ───────────────────────────────────────────
# Админ: список заказов
# ───────────────────────────────────────────
@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = get_pending_orders()
    if not rows:
        await message.answer("✅ Нет необработанных заказов!")
        return

    text = f"📋 *Ожидают доставки: {len(rows)}*\n\n"
    buttons = []
    for row in rows:
        payload, user_id, username, gift_name, stars, created_at = row
        text += f"• {gift_name} | {username} | {stars}⭐ | {created_at[11:16]}\n"
        buttons.append([InlineKeyboardButton(
            text=f"✅ {gift_name} → {username}",
            callback_data=f"done:{payload}"
        )])

    await message.answer(text, parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ───────────────────────────────────────────
# Админ: вся история
# ───────────────────────────────────────────
@dp.message(Command("history"))
async def cmd_history(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = get_all_orders()
    if not rows:
        await message.answer("История пуста")
        return

    total_stars = sum(r[6] for r in rows)
    delivered = sum(1 for r in rows if r[7] == "delivered")

    text = (
        f"📊 *Статистика (последние 50)*\n\n"
        f"Всего заказов: {len(rows)}\n"
        f"Доставлено: {delivered}\n"
        f"Ожидают: {len(rows) - delivered}\n"
        f"Stars получено: {total_stars} ⭐\n\n"
    )
    for r in rows[:15]:
        status_icon = "✅" if r[7] == "delivered" else "⏳"
        text += f"{status_icon} {r[5]} | {r[3]} | {r[6]}⭐ | {r[8][5:16]}\n"

    await message.answer(text, parse_mode="Markdown")

# ───────────────────────────────────────────
# Пользователь: мои заказы
# ───────────────────────────────────────────
@dp.message(Command("myorders"))
async def cmd_myorders(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("orders.db")
    rows = conn.execute(
        "SELECT gift_name, stars, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
        (user_id,)
    ).fetchall()
    conn.close()

    if not rows:
        await message.answer("У тебя пока нет заказов. /catalog — смотри подарки!")
        return

    text = "📦 *Твои заказы:*\n\n"
    for gift_name, stars, status, created_at in rows:
        icon = "✅" if status == "delivered" else "⏳"
        text += f"{icon} {gift_name} | {stars}⭐ | {created_at[5:16]}\n"

    await message.answer(text, parse_mode="Markdown")

# ───────────────────────────────────────────
# Помощь
# ───────────────────────────────────────────
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "🔧 *Команды администратора:*\n\n"
            "/orders — заказы ожидающие доставки\n"
            "/history — история всех заказов\n"
            "/catalog — каталог подарков\n\n"
            "📌 *Процесс:*\n"
            "1. Приходит уведомление о новом заказе\n"
            "2. Открываешь Telegram, идёшь в профиль покупателя\n"
            "3. Нажимаешь «Отправить подарок»\n"
            "4. Возвращаешься в бот, нажимаешь ✅ Отправил",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "ℹ️ *Как это работает:*\n\n"
            "1. /catalog — выбираешь подарок\n"
            "2. Оплачиваешь Stars прямо в Telegram\n"
            "3. Получаешь подарок в течение 10 минут\n\n"
            "/myorders — твои заказы\n"
            "/catalog — каталог",
            parse_mode="Markdown"
        )

# ───────────────────────────────────────────
# Запуск
# ───────────────────────────────────────────
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    init_db()
    logging.info("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
