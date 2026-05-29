import asyncio
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = "8551024830:AAGJ3oikXbKBrzEQ-ge13wUJTNanEllK1Tk"
ADMIN_ID = 6852628550

DB = "support.db"


# ---------------- BOT ----------------
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


# ---------------- FSM ----------------
class AdminState(StatesGroup):
    waiting_answer = State()


# ---------------- DB ----------------
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            status TEXT DEFAULT 'open'
        )
        """)
        await db.commit()


# ---------------- START ----------------
@dp.message(CommandStart())
async def start(message: types.Message):
    sent = await message.answer(
        "👋 Поддержка онлайн\n\n"
        "Отправьте сообщение или фото с описанием проблемы."
    )

    # удаление приветствия через 30 сек
    await asyncio.sleep(30)

    try:
        await sent.delete()
    except:
        pass


# ---------------- USER MESSAGE / PHOTO ----------------
@dp.message(F.from_user.id != ADMIN_ID)
async def user_message(message: types.Message):

    text = message.text or message.caption or "Без текста"

    # сохраняем тикет
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "INSERT INTO tickets (user_id, username, message) VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.username, text)
        )
        ticket_id = cursor.lastrowid
        await db.commit()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Ответить",
                    callback_data=f"reply_{ticket_id}"
                )
            ]
        ]
    )

    caption = (
        f"📩 <b>Тикет #{ticket_id}</b>\n\n"
        f"USER_ID: {message.from_user.id}\n"
        f"USERNAME: @{message.from_user.username}\n\n"
        f"{text}"
    )

    # ---------- PHOTO ----------
    if message.photo:

        largest_photo = message.photo[-1].file_id

        await bot.send_photo(
            ADMIN_ID,
            photo=largest_photo,
            caption=caption,
            reply_markup=kb
        )

    # ---------- TEXT ----------
    else:

        await bot.send_message(
            ADMIN_ID,
            caption,
            reply_markup=kb
        )

    # ---------- USER SUCCESS MESSAGE ----------
    sent_message = await message.answer(
        "📨 Сообщение отправлено в поддержку"
    )

    # ждём 30 секунд
    await asyncio.sleep(30)

    # удаляем сообщения
    try:
        await message.delete()
    except:
        pass

    try:
        await sent_message.delete()
    except:
        pass


# ---------------- CLICK REPLY ----------------
@dp.callback_query(F.data.startswith("reply_"))
async def reply_callback(callback: types.CallbackQuery, state: FSMContext):

    if callback.from_user.id != ADMIN_ID:
        return

    ticket_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT user_id FROM tickets WHERE id=?",
            (ticket_id,)
        )
        row = await cursor.fetchone()

    if not row:
        await callback.answer("❌ Тикет не найден", show_alert=True)
        return

    user_id = row[0]

    # сохраняем user_id
    await state.update_data(user_id=user_id)

    await state.set_state(AdminState.waiting_answer)

    await callback.message.answer("✍️ Введите ответ пользователю:")
    await callback.answer()


# ---------------- SEND ANSWER ----------------
@dp.message(AdminState.waiting_answer, F.from_user.id == ADMIN_ID)
async def send_answer(message: types.Message, state: FSMContext):

    data = await state.get_data()
    user_id = data.get("user_id")

    if not user_id:
        await message.answer("❌ user_id не найден")
        await state.clear()
        return

    try:
        await bot.send_message(
            user_id,
            f"📩 <b>Ответ поддержки:</b>\n\n{message.text}"
        )

        success = await message.answer("✅ Ответ отправлен")

        print("SEND OK ->", user_id)

        # удаление сообщения об успехе
        await asyncio.sleep(15)

        try:
            await success.delete()
        except:
            pass

    except Exception as e:
        print("SEND ERROR:", e)
        await message.answer(f"❌ Ошибка: {e}")

    await state.clear()


# ---------------- MAIN ----------------
async def main():
    await init_db()
    print("✅ BOT STARTED")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())