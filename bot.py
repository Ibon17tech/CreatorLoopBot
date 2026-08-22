import os
import asyncio
import aiosqlite

from dotenv import load_dotenv
from keep_alive import keep_alive
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

keep_alive()

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
GROUP_ID = os.getenv("GROUP_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_NAME = "creatorloop.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Applications jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                name TEXT,
                youtube_url TEXT,
                niche TEXT,
                experience TEXT,
                goals TEXT,
                skills TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Creators jadvali (Qabul qilinganlar)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                youtube_url TEXT,
                niche TEXT,
                status TEXT DEFAULT 'active',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Video submissions jadvali (Limit va statistika uchun)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS video_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

bot = Bot(token=BOT_TOKEN)

class Application(StatesGroup):
    name = State()
    youtube = State()
    niche = State()
    experience = State()
    goals = State()
    skills = State()

class VideoSubmission(StatesGroup):
    waiting_for_url = State()

dp = Dispatcher(storage=MemoryStorage())

async def check_user_membership(user_id: int) -> tuple[bool, bool]:
    """User guruh va kanalda bor-yo'qligini tekshiradi (is_group, is_channel)"""
    is_group = False
    is_channel = False

    if GROUP_ID:
        try:
            member = await bot.get_chat_member(chat_id=int(GROUP_ID), user_id=user_id)
            if member.status in ["creator", "administrator", "member", "restricted"]:
                is_group = True
        except Exception:
            is_group = False

    if CHANNEL_ID:
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            if member.status in ["creator", "administrator", "member"]:
                is_channel = True
        except Exception:
            is_channel = False

    return is_group, is_channel


async def check_daily_video_limit(user_id: int) -> bool:
    """Foydalanuvchi oxirgi 24 soat ichida 2 tadan kam video yuborganini tekshiradi"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM video_submissions WHERE telegram_id = ? AND created_at >= datetime('now', '-1 day')",
            (user_id,)
        ) as cursor:
            count = await cursor.fetchone()
            return count[0] < 2


# =========================
# DINAMIK MENYU TUGMALARI
# =========================
async def get_main_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Foydalanuvchi holatiga qarab menyu tugmalarini shakllantiradi"""
    is_approved = False
    
    # Bazadan tekshirish
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT status FROM creators WHERE telegram_id = ? AND status = 'active'", (user_id,)) as cursor:
            creator = await cursor.fetchone()
            if creator:
                is_approved = True

    # Kanallar va guruhga a'zolikni tekshirish
    in_group, in_channel = await check_user_membership(user_id)
    
    keyboard_buttons = []
    
    # Faqat arizasi tasdiqlangan va har ikkala manbaga a'zo foydalanuvchida paydo bo'ladi
    if is_approved and in_group and in_channel:
        keyboard_buttons.append([KeyboardButton(text="🎬 Yangi video yuborish")])
        
    keyboard_buttons.append([KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📜 Qoidalar")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)


# =========================
# RULES & STATS COMMANDS
# =========================

@dp.message(F.text == "📜 Qoidalar")
@dp.message(Command("rules"))
async def show_rules(message: Message):
    rules_text = (
        "<b>📜 CreatorLoop Hamjamiyati Qoidalari</b>\n\n"
        "1. <b>Talablar:</b> O'zbekistonlik YouTube creator, kamida 500+ subscriber va kanal ochilganiga 1 oydan oshgan bo'lishi kerak.\n"
        "2. <b>Mavzu cheklovlari:</b> O'zbekiston qonunchiligiga zid, diniy va siyosiy bahsli kontentlar qabul qilinmaydi.\n"
        "3. <b>Kontent sifati:</b> Spam, scam va reklama xarakteridagi videolar taqiqlanadi.\n"
        "4. <b>O'zaro yordam (Feedback):</b> Kanalda e'lon qilingan boshqa creatorlarning videolariga xolis va sifatli feedback berish majburiy.\n"
        "5. <b>Faollik:</b> Hamjamiyatda faol bo'lmagan a'zolar avtomatik ravishda safdan chiqarilishi mumkin."
    )
    kb = await get_main_keyboard(message.from_user.id)
    await message.answer(rules_text, reply_markup=kb, parse_mode="HTML")


@dp.message(F.text == "📊 Statistika")
@dp.message(Command("stats"))
async def show_stats(message: Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM creators WHERE status = 'active'") as cursor:
            active_creators = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM video_submissions WHERE status = 'published'") as cursor:
            published_videos = (await cursor.fetchone())[0]

    stats_text = (
        "<b>📊 CreatorLoop Real-time Statistikasi</b>\n\n"
        f"👥 <b>Faol Creatorlar:</b> {active_creators} ta\n"
        f"🎬 <b>Chiqarilgan Videolar:</b> {published_videos} ta\n\n"
        "<i>Eslatma: Ushbu ma'lumotlar bazadan avtomatik hisoblanadi.</i>"
    )
    kb = await get_main_keyboard(message.from_user.id)
    await message.answer(stats_text, reply_markup=kb, parse_mode="HTML")


# =========================
# /start
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Ariza topshirish", callback_data="apply")],
            [InlineKeyboardButton(text="ℹ️ CreatorLoop haqida", callback_data="about")]
        ]
    )

    kb = await get_main_keyboard(message.from_user.id)

    await message.answer(
        "👋 <b>CreatorLoop'ga xush kelibsiz!</b>\n\n"
        "🇺🇿 O‘zbekistonlik YouTube creatorlar uchun yopiq creator hamjamiyati.\n\n"
        "Bu yerda creatorlar bir-biriga feedback beradi, tajriba almashadi, collaboration qiladi va birga rivojlanadi.\n\n"
        "🎯 Maqsadimiz — shunchaki ko‘p creator yig‘ish emas, <b>faol va kuchli community</b> qurish.",
        reply_markup=inline_keyboard,
        parse_mode="HTML"
    )
    # Menyuni ham yangilab qo'yamiz
    await message.answer("Menyu faollashtirildi 👇", reply_markup=kb)


# =========================
# CreatorLoop haqida
# =========================

@dp.callback_query(F.data == "about")
async def about_handler(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Ariza topshirish", callback_data="apply")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_start")]
        ]
    )

    await callback.message.edit_text(
        "🎬 <b>CreatorLoop nima?</b>\n\n"
        "CreatorLoop — O‘zbekistonlik YouTube creatorlar uchun yaratilayotgan yopiq community.\n\n"
        "Bu yerda creatorlar:\n\n"
        "🎬 Videolariga feedback oladi\n"
        "💬 Boshqa creatorlar bilan fikr almashadi\n"
        "🤝 Collaboration qiladi\n"
        "💡 Tajriba almashadi\n"
        "🚀 Birgalikda rivojlanadi\n\n"
        "Bizning maqsadimiz — kichik bo‘lsa ham <b>faol va sifatli creatorlar hamjamiyatini</b> qurish.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# =========================
# Ariza boshlanishi
# =========================

@dp.callback_query(F.data == "apply")
async def apply_handler(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Shartlar bilan tanishdim", callback_data="accepted_rules")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_start")]
        ]
    )

    await callback.message.edit_text(
        "📋 <b>CreatorLoop'ga qo‘shilish shartlari</b>\n\n"
        "🇺🇿 O‘zbekistonlik creator bo‘lish\n"
        "📅 YouTube kanali kamida 1 oy oldin ochilgan bo‘lishi\n"
        "👥 500+ obunachiga ega bo‘lishi\n"
        "🎬 YouTube'da faol kontent yaratishi\n"
        "⚖️ O‘zbekiston qonunchiligiga zid bo‘lmagan mavzularda kontent yaratishi\n"
        "🤝 Boshqa creatorlar bilan foydali fikr almashishga tayyor bo‘lishi\n\n"
        "💡 500 obunachidan kam bo‘lgan creatorlar ham alohida ko‘rib chiqilishi mumkin.\n\n"
        "👀 Har bir ariza admin tomonidan qo‘lda ko‘rib chiqiladi.\n\n"
        "Shartlar bilan tanishib chiqqan bo‘lsangiz, davom etishingiz mumkin.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# =========================
# Shartlar tasdiqlandi & FSM
# =========================

@dp.callback_query(F.data == "accepted_rules")
async def accepted_rules_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Application.name)
    await callback.message.edit_text(
        "🚀 <b>Ajoyib!</b>\n\nArizangizni to‘ldirishni boshlaymiz.\n\nAvval ismingizni kiriting:",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(Application.name)
async def name_handler(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Ismingiz juda qisqa.\n\nIltimos, ismingizni qaytadan kiriting:")
        return

    await state.update_data(name=name)
    await state.set_state(Application.youtube)

    await message.answer(
        f"Rahmat, <b>{name}</b>! ✅\n\n📺 Endi YouTube kanalingiz havolasini yuboring.\n\nMasalan:\n<code>https://youtube.com/@username</code>",
        parse_mode="HTML"
    )

@dp.message(Application.youtube)
async def youtube_handler(message: Message, state: FSMContext):
    youtube_url = message.text.strip()

    if not (
        youtube_url.startswith("youtube.com/")
        or youtube_url.startswith("www.youtube.com/")
        or youtube_url.startswith("https://youtube.com/")
        or youtube_url.startswith("https://www.youtube.com/")
        or youtube_url.startswith("http://youtube.com/")
        or youtube_url.startswith("http://www.youtube.com/")
    ):
        await message.answer(
            "❌ Bu YouTube kanal havolasiga o‘xshamayapti.\n\nIltimos, YouTube kanalingiz havolasini yuboring.\n\nMasalan:\n<code>https://youtube.com/@username</code>",
            parse_mode="HTML"
        )
        return

    await state.update_data(youtube_url=youtube_url)
    await state.set_state(Application.niche)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚽ Futbol", callback_data="niche_football"), InlineKeyboardButton(text="🎮 Gaming", callback_data="niche_gaming")],
            [InlineKeyboardButton(text="💻 Texnologiya", callback_data="niche_tech"), InlineKeyboardButton(text="📚 Ta'lim", callback_data="niche_education")],
            [InlineKeyboardButton(text="🎥 Vlog", callback_data="niche_vlog"), InlineKeyboardButton(text="🎭 Ko‘ngilochar", callback_data="niche_entertainment")],
            [InlineKeyboardButton(text="📰 Yangiliklar", callback_data="niche_news"), InlineKeyboardButton(text="🎨 Boshqa", callback_data="niche_other")]
        ]
    )

    await message.answer("Ajoyib! 📺 YouTube kanalingiz qabul qilindi.\n\nEndi kontentingizning asosiy yo‘nalishini tanlang:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("niche_"))
async def niche_handler(callback: CallbackQuery, state: FSMContext):
    niche_map = {
        "niche_football": "⚽ Futbol", "niche_gaming": "🎮 Gaming", "niche_tech": "💻 Texnologiya",
        "niche_education": "📚 Ta'lim", "niche_vlog": "🎥 Vlog", "niche_entertainment": "🎭 Ko‘ngilochar",
        "niche_news": "📰 Yangiliklar", "niche_other": "🎨 Boshqa"
    }

    niche = niche_map.get(callback.data)

    await state.update_data(niche=niche)
    await state.set_state(Application.experience)

    await callback.message.edit_text(
        f"✅ Yo‘nalish: <b>{niche}</b>\n\n📅 YouTube'da qancha vaqtdan beri kontent yaratasiz?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1–3 oy", callback_data="exp_1_3"), InlineKeyboardButton(text="3–6 oy", callback_data="exp_3_6")],
                [InlineKeyboardButton(text="6–12 oy", callback_data="exp_6_12"), InlineKeyboardButton(text="1–2 yil", callback_data="exp_1_2")],
                [InlineKeyboardButton(text="2+ yil", callback_data="exp_2_plus")]
            ]
        ),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("exp_"))
async def experience_handler(callback: CallbackQuery, state: FSMContext):
    experience_map = {
        "exp_1_3": "1–3 oy", "exp_3_6": "3–6 oy", "exp_6_12": "6–12 oy",
        "exp_1_2": "1–2 yil", "exp_2_plus": "2+ yil"
    }

    experience = experience_map.get(callback.data)

    await state.update_data(experience=experience, goals=[])
    await state.set_state(Application.goals)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Feedback", callback_data="goal_feedback"), InlineKeyboardButton(text="🤝 Collaboration", callback_data="goal_collab")],
            [InlineKeyboardButton(text="👥 Networking", callback_data="goal_networking"), InlineKeyboardButton(text="💡 Tajriba almashish", callback_data="goal_experience")],
            [InlineKeyboardButton(text="🚀 Birga rivojlanish", callback_data="goal_growth")],
            [InlineKeyboardButton(text="➡️ Davom etish", callback_data="goals_done")]
        ]
    )

    await callback.message.edit_text(
        f"📅 Tajriba: <b>{experience}</b>\n\n🎯 <b>CreatorLoop'dan nimani kutyapsiz?</b>\n\nBir nechta variantni tanlashingiz mumkin.\nTanlaganlaringiz yonida ✅ paydo bo‘ladi.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(Application.goals, F.data == "goals_done")
async def goals_done_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    goals = data.get("goals", [])

    if not goals:
        await callback.answer("Avval kamida bitta variantni tanlang.", show_alert=True)
        return

    await state.set_state(Application.skills)

    await callback.message.edit_text(
        "💡 <b>Endi communityga nima bera olishingizni yozing.</b>\n\nMasalan:\n• YouTube bo‘yicha tajriba\n• Video editing\n• Thumbnail\n• Ssenariy yozish\n• Feedback berish\n• Collaboration\n\nO‘zingizga mos keladigan narsalarni yozing:",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(Application.goals, F.data.startswith("goal_"))
async def goal_toggle_handler(callback: CallbackQuery, state: FSMContext):
    goal_map = {
        "goal_feedback": "💬 Feedback", "goal_collab": "🤝 Collaboration",
        "goal_networking": "👥 Networking", "goal_experience": "💡 Tajriba almashish",
        "goal_growth": "🚀 Birga rivojlanish"
    }

    goal = goal_map.get(callback.data)
    data = await state.get_data()
    goals = data.get("goals", [])

    if goal in goals:
        goals.remove(goal)
    else:
        goals.append(goal)

    await state.update_data(goals=goals)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=("✅ " if "💬 Feedback" in goals else "") + "💬 Feedback", callback_data="goal_feedback"),
                InlineKeyboardButton(text=("✅ " if "🤝 Collaboration" in goals else "") + "🤝 Collaboration", callback_data="goal_collab")
            ],
            [
                InlineKeyboardButton(text=("✅ " if "👥 Networking" in goals else "") + "👥 Networking", callback_data="goal_networking"),
                InlineKeyboardButton(text=("✅ " if "💡 Tajriba almashish" in goals else "") + "💡 Tajriba almashish", callback_data="goal_experience")
            ],
            [
                InlineKeyboardButton(text=("✅ " if "🚀 Birga rivojlanish" in goals else "") + "🚀 Birga rivojlanish", callback_data="goal_growth")
            ],
            [InlineKeyboardButton(text="➡️ Davom etish", callback_data="goals_done")]
        ]
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()

@dp.message(Application.skills)
async def skills_handler(message: Message, state: FSMContext):
    skills = message.text.strip()

    if len(skills) < 3:
        await message.answer("❌ Javobingiz juda qisqa.\n\nIltimos, communityga qanday foyda bera olishingizni biroz batafsilroq yozing:")
        return

    await state.update_data(skills=skills)
    data = await state.get_data()

    goals_formatted = "\n".join([f"• {g}" for g in data.get("goals", [])])

    preview_text = (
        "📋 <b>ARIZANGIZNI TASDIQLANG</b>\n\n"
        f"👤 <b>Ism:</b> {data.get('name')}\n"
        f"📺 <b>YouTube:</b> {data.get('youtube_url')}\n"
        f"🎬 <b>Yo‘nalish:</b> {data.get('niche')}\n"
        f"📅 <b>Tajriba:</b> {data.get('experience')}\n\n"
        f"🎯 <b>CreatorLoop'dan kutganlaringiz:</b>\n{goals_formatted}\n\n"
        f"💡 <b>Communityga bera oladigan foydangiz:</b>\n{data.get('skills')}\n\n"
        "Ma'lumotlar to‘g‘rimi?"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Arizani yuborish", callback_data="submit_application")],
            [InlineKeyboardButton(text="✏️ Qayta to‘ldirish", callback_data="accepted_rules")]
        ]
    )

    await message.answer(preview_text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(F.data == "submit_application")
async def submit_application_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user

    goals_formatted = "\n".join([f"• {g}" for g in data.get("goals", [])])
    goals_str = ", ".join(data.get("goals", []))

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO applications (telegram_id, username, name, youtube_url, niche, experience, goals, skills, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=EXCLUDED.username,
                name=EXCLUDED.name,
                youtube_url=EXCLUDED.youtube_url,
                niche=EXCLUDED.niche,
                experience=EXCLUDED.experience,
                goals=EXCLUDED.goals,
                skills=EXCLUDED.skills,
                status='pending'
        """, (
            user.id,
            user.username or "",
            data.get('name'),
            data.get('youtube_url'),
            data.get('niche'),
            data.get('experience'),
            goals_str,
            data.get('skills')
        ))
        await db.commit()

    await callback.message.edit_text(
        "🎉 <b>Arizangiz qabul qilindi!</b>\n\nAdminlar arizangizni va YouTube kanalingizni ko‘rib chiqishadi.\nNatija tez orada ushbu bot orqali yuboriladi.",
        parse_mode="HTML"
    )

    admin_text = (
        "🆕 <b>YANGI CREATORLOOP ARIZASI</b>\n\n"
        f"👤 <b>Ism:</b> {data.get('name')}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"✈️ <b>Username:</b> @{user.username if user.username else 'yo-q'}\n"
        f"📺 <b>YouTube URL:</b> {data.get('youtube_url')}\n"
        f"🎬 <b>Niche:</b> {data.get('niche')}\n"
        f"📅 <b>Tajriba:</b> {data.get('experience')}\n\n"
        f"🎯 <b>Maqsadlar:</b>\n{goals_formatted}\n\n"
        f"💡 <b>Bera oladigan foydasi:</b>\n{data.get('skills')}"
    )

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user.id}")
            ]
        ]
    )

    if ADMIN_ID:
        try:
            await bot.send_message(chat_id=int(ADMIN_ID), text=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
        except Exception as e:
            print(f"Adminga xabar yuborishda xatolik: {e}")

    await state.clear()
    await callback.answer()


# =========================
# Admin User Application Handlers
# =========================

@dp.callback_query(F.data.startswith("approve_"))
async def approve_user_handler(callback: CallbackQuery):
    target_user_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE applications SET status = 'accepted' WHERE telegram_id = ?", (target_user_id,))
        
        async with db.execute("SELECT name, youtube_url, niche FROM applications WHERE telegram_id = ?", (target_user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                name, youtube_url, niche = row
                await db.execute("""
                    INSERT INTO creators (telegram_id, name, youtube_url, niche)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET status='active'
                """, (target_user_id, name, youtube_url, niche))
        
        await db.commit()

    group_invite_link = None
    if GROUP_ID:
        try:
            link = await bot.create_chat_invite_link(chat_id=int(GROUP_ID), member_limit=1)
            group_invite_link = link.invite_link
        except Exception as e:
            print(f"Guruh linkida xatolik: {e}")

    channel_invite_link = None
    if CHANNEL_ID:
        try:
            if str(CHANNEL_ID).startswith("-100"):
                link = await bot.create_chat_invite_link(chat_id=int(CHANNEL_ID))
                channel_invite_link = link.invite_link
            elif str(CHANNEL_ID).startswith("@"):
                channel_invite_link = f"https://t.me/{CHANNEL_ID.replace('@', '')}"
            else:
                channel_invite_link = f"https://t.me/{CHANNEL_ID}"
        except Exception as e:
            print(f"Kanal linkida xatolik: {e}")

    try:
        text = (
            "🎉 <b>Tabriklaymiz! Siz CreatorLoop hamjamiyatiga qabul qilindingiz!</b>\n\n"
            "Davom etish va videolarni ulashish uchun quyidagi resurslarga qo'shiling:\n\n"
        )
        if group_invite_link:
            text += f"👥 <b>Yopiq Guruh:</b>\n{group_invite_link}\n\n"
        
        if channel_invite_link:
            text += f"📢 <b>Asosiy Kanal:</b>\n{channel_invite_link}\n\n"
            
        text += (
            "📌 <b>Video yuborish tartibi va qoidalari:</b>\n"
            "• Faqat arizada ko'rsatilgan <b>shaxsiy YouTube kanalingizga</b> yuklangan videolarni yuborishingiz mumkin.\n"
            "• Yuborilgan videolar hamjamiyat kanalida e'lon qilinadi va boshqa creatorlardan <b>xolis feedback (fikr-mulohaza)</b> olasiz.\n"
            "• Kunlik video yuborish cheklovi: <b>max 2 ta video</b>.\n\n"
            "⚠️ <i>Eslatma: Kanal hamda guruhga to'liq qo'shilganingizdan so'ng, menyuda '🎬 Yangi video yuborish' tugmasi avtomatik paydo bo'ladi!</i>"
        )

        kb = await get_main_keyboard(target_user_id)
        await bot.send_message(chat_id=target_user_id, text=text, reply_markup=kb, parse_mode="HTML")
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>QABUL QILINDI</b>", parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"Xabar yuborishda xatolik: {e}", show_alert=True)

    await callback.answer()


@dp.callback_query(F.data.startswith("reject_"))
async def reject_user_handler(callback: CallbackQuery):
    target_user_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE applications SET status = 'rejected' WHERE telegram_id = ?", (target_user_id,))
        await db.commit()

    try:
        kb = await get_main_keyboard(target_user_id)
        await bot.send_message(
            chat_id=target_user_id,
            text="Afsuski, hozircha CreatorLoop'ga qabul qilina olmadingiz.\n\nRivojlanishdan to'xtamang! Keyinchalik qayta ariza topshirishingiz mumkin.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>RAD ETILDI</b>", parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"Foydalanuvchiga xabar yuborib bo'lmadi: {e}", show_alert=True)

    await callback.answer()


@dp.callback_query(F.data == "back_start")
async def back_start_handler(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Ariza topshirish", callback_data="apply")],
            [InlineKeyboardButton(text="ℹ️ CreatorLoop haqida", callback_data="about")]
        ]
    )

    await callback.message.edit_text(
        "👋 <b>CreatorLoop'ga xush kelibsiz!</b>\n\n🇺🇿 O‘zbekistonlik YouTube creatorlar uchun yopiq creator hamjamiyati.\n\n🎯 <b>Faol creatorlar. Real feedback. Birgalikda rivojlanish.</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# =========================
# Admin Panel Commands
# =========================

@dp.message(F.text == "/admin")
async def admin_panel_handler(message: Message):
    if not ADMIN_ID or str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Bu buyruq faqat adminlar uchun!")
        return

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT telegram_id, name, youtube_url, niche, status FROM applications ORDER BY id DESC"
        ) as cursor:
            applications = await cursor.fetchall()

    if not applications:
        await message.answer("ℹ️ Hozircha bazada birorta ham ariza yo'q.")
        return

    pending_apps = [a for a in applications if a[4] == 'pending']
    accepted_apps = [a for a in applications if a[4] == 'accepted']
    rejected_apps = [a for a in applications if a[4] == 'rejected']

    text = f"⚙️ <b>CREATORLOOP USERLAR RO'YXATI</b> (Jami: {len(applications)} ta)\n\n"

    text += f"✅ <b>Qabul qilinganlar ({len(accepted_apps)}):</b>\n"
    if accepted_apps:
        for app in accepted_apps:
            telegram_id, name, youtube_url, niche, status = app
            text += f"• <b>{name}</b> ({niche}) — <a href='{youtube_url}'>YouTube Kanal</a>\n"
    else:
        text += "<i>Hozircha yo'q</i>\n"

    text += "\n"

    text += f"❌ <b>Rad etilganlar ({len(rejected_apps)}):</b>\n"
    if rejected_apps:
        for app in rejected_apps:
            telegram_id, name, youtube_url, niche, status = app
            text += f"• <b>{name}</b> ({niche})\n"
    else:
        text += "<i>Hozircha yo'q</i>\n"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

    if pending_apps:
        await message.answer(
            f"⏳ <b>Kutilayotgan arizalar ({len(pending_apps)} ta):</b>\nQuyida ularni tasdiqlashingiz mumkin 👇",
            parse_mode="HTML"
        )
        for app in pending_apps:
            telegram_id, name, youtube_url, niche, status = app
            app_text = (
                f"👤 <b>Ism:</b> {name}\n"
                f"📺 <b>YouTube:</b> {youtube_url}\n"
                f"🎬 <b>Niche:</b> {niche}\n"
                f"🆔 <b>ID:</b> <code>{telegram_id}</code>"
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"approve_{telegram_id}"),
                        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{telegram_id}")
                    ]
                ]
            )
            await message.answer(app_text, reply_markup=keyboard, parse_mode="HTML")


# =========================
# VIDEO SUBMISSION PROCESS
# =========================

@dp.message(F.text == "🎬 Yangi video yuborish")
@dp.callback_query(F.data == "submit_video")
async def start_video_submission(event: Message | CallbackQuery, state: FSMContext):
    user_id = event.from_user.id

    in_group, in_channel = await check_user_membership(user_id)
    kb = await get_main_keyboard(user_id)

    if not in_group or not in_channel:
        missing = []
        if not in_group:
            missing.append("• Yopiq Guruhimizga")
        if not in_channel:
            missing.append("• Asosiy Kanalimizga")

        missing_str = "\n".join(missing)
        text = (
            f"⚠️ <b>Video yuborish uchun a'zolik talab etiladi!</b>\n\n"
            f"Siz quyidagilarga a'zo emassiz yoki chiqib ketgansiz:\n"
            f"{missing_str}\n\n"
            f"Iltimos, avval ularga qo'shiling va qayta urinib ko'ring!"
        )
        if isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    can_submit = await check_daily_video_limit(user_id)
    if not can_submit:
        text = (
            "⚠️ <b>Kunlik limitga yetdingiz!</b>\n\n"
            "Siz bugun allaqachon 2 ta video yuborgansiz. "
            "Kanal sifatini saqlash uchun kuniga ko'pi bilan 2 ta video yuborish mumkin.\n\n"
            "Keyingi videongizni ertaga yuborishingiz mumkin. 😊"
        )
        if isinstance(event, CallbackQuery):
            await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    await state.clear()
    await state.set_state(VideoSubmission.waiting_for_url)
    
    msg_text = (
        "🎬 <b>Yangi YouTube videongiz havolasini (link) yuboring:</b>\n\n"
        "Masalan:\n<code>https://youtu.be/dQw4w9WgXcQ</code>"
    )
    
    if isinstance(event, CallbackQuery):
        await event.message.answer(msg_text, parse_mode="HTML")
        await event.answer()
    else:
        await event.answer(msg_text, parse_mode="HTML")


@dp.message(VideoSubmission.waiting_for_url)
async def process_video_url(message: Message, state: FSMContext):
    url = message.text.strip()
    kb = await get_main_keyboard(message.from_user.id)

    if not ("youtube.com" in url or "youtu.be" in url):
        await message.answer("❌ Bu YouTube video havolasiga o'xshamayapti. Qayta yuborib ko'ring:")
        return

    user = message.from_user

    can_submit = await check_daily_video_limit(user.id)
    if not can_submit:
        await state.clear()
        await message.answer(
            "⚠️ <b>Kunlik limitga yetdingiz!</b>\n\n"
            "Siz bugun allaqachon 2 ta video yuborgansiz. "
            "Keyingi videongizni ertaga yuborishingiz mumkin. 😊",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO video_submissions (telegram_id, status) VALUES (?, 'pending')", (user.id,))
        await db.commit()

    await state.clear()

    await message.answer(
        "✅ Videongiz qabul qilindi va admin moderatsiyasiga yuborildi!\n"
        "Tasdiqlangach, CreatorLoop kanalida e'lon qilinadi.",
        reply_markup=kb
    )

    admin_text = (
        "🎬 <b>YANGI VIDEO MODERATSIYASI</b>\n\n"
        f"👤 <b>Creator:</b> {user.full_name}\n"
        f"✈️ <b>Username:</b> @{user.username if user.username else 'yo-q'}\n"
        f"🔗 <b>Video Link:</b> {url}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Kanalga chiqarish", callback_data=f"pub_v_{user.id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej_v_{user.id}")
            ]
        ]
    )

    if ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=int(ADMIN_ID),
                text=admin_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Adminga xabar yuborishda xatolik: {e}")


@dp.callback_query(F.data.startswith("pub_v_"))
async def publish_video_handler(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])

    text_lines = callback.message.text.split("\n")
    video_url = text_lines[-1].replace("Video Link: ", "").strip()
    creator_info = text_lines[2].replace("Creator: ", "").strip()

    post_text = (
        "🎬 <b>YANGI VIDEO!</b>\n\n"
        f"👤 <b>Creator:</b> {creator_info}\n\n"
        f"🔗 <b>Video linki:</b> {video_url}\n\n"
        "💬 <b>Feedback qoldiring:</b>\n"
        "Videoni tomosha qiling va pastdagi izohlar bo'limida videoning kuchli/o'stirish kerak bo'lgan taraflari haqida o'z fikringizni yozib qoldiring!"
    )

    if CHANNEL_ID:
        try:
            await bot.send_message(chat_id=CHANNEL_ID, text=post_text, parse_mode="HTML")
            
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute("UPDATE video_submissions SET status = 'published' WHERE telegram_id = ? AND status = 'pending'", (user_id,))
                await db.commit()

            kb = await get_main_keyboard(user_id)
            await bot.send_message(
                chat_id=user_id,
                text="🎉 <b>Tabriklaymiz!</b> Videongiz kanalga joylandi.",
                reply_markup=kb,
                parse_mode="HTML"
            )

            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>KANALGA CHIQARILDI</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            await callback.answer(f"Xatolik yuz berdi: {e}", show_alert=True)
            return

    await callback.answer()


@dp.callback_query(F.data.startswith("rej_v_"))
async def reject_video_handler(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[-1])

    try:
        kb = await get_main_keyboard(user_id)
        await bot.send_message(
            chat_id=user_id,
            text="❌ Afsuski, siz yuborgan video adminga ma'qul kelmadi va rad etildi.",
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Foydalanuvchiga rad xabarini yuborishda xatolik: {e}")

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>VIDEO RAD ETILDI</b>",
        parse_mode="HTML"
    )
    await callback.answer()


# =========================
# Main
# =========================

async def main():
    await init_db()
    print("CreatorLoop bot va Baza ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())