from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatPermissions
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_ID
from database import (
    add_or_update_chat, get_all_chats,
    add_bad_word, remove_bad_word, list_bad_words,
    get_mute_minutes, set_mute_minutes, add_whitelist_user,
    remove_whitelist_user, list_whitelist, is_whitelisted,
    add_or_update_user, get_all_users, get_user_by_id
)
from utils.file_export import export_chats_to_txt, export_chats_to_pdf

import asyncio
import re
from datetime import timedelta, datetime, timezone

# ================== SETTINGS ==================
USERS_PER_PAGE = 10
UNSAFE_EXT = {".apk", ".js", ".bat", ".exe", ".scr", ".vbs", ".cmd", ".msi", ".reg", ".ps1"}

router = Router()

# ================== STATES ==================
class BadWordStates(StatesGroup):
    add_scope = State()       # not used (we drive by buttons). kept for clarity
    add_words = State()
    remove_words = State()

class WhitelistStates(StatesGroup):
    add_choose_chat = State()
    add_enter_user = State()
    rem_choose_chat = State()
    rem_enter_user = State()

class MuteStates(StatesGroup):
    choose_chat = State()
    enter_minutes = State()

class MediaState(StatesGroup):
    waiting_media = State()

# ================== HELPERS ==================

def is_admin(user_id: int) -> bool:
    return bool(user_id in ADMIN_ID)


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📊 Statistikalar", callback_data="stats"),
         InlineKeyboardButton(text="📄 TXT eksport", callback_data="export:txt")],
        [InlineKeyboardButton(text="📑 PDF eksport", callback_data="export:pdf"),
         InlineKeyboardButton(text="🖼 Media post", callback_data="media:start")],
        [InlineKeyboardButton(text="🛡 Yomon so‘zlar", callback_data="bw:menu"),
         InlineKeyboardButton(text="⏱ Mute davomiyligi", callback_data="mute:menu")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="users:page:0"),
         InlineKeyboardButton(text="🛡 Fayl ruxsatlari", callback_data="wh:menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")]])


# ================== START / HELP ==================
@router.message(Command("start"))
async def start_handler(message: types.Message):
    chat_type = message.chat.type

    # 1) Foydalanuvchini bazaga yozamiz (private/group farqsiz)
    await add_or_update_user(message.from_user)

    # 2) Guruh/kanal bo'lsa chatni ham bazaga yozamiz
    if chat_type in ["group", "supergroup", "channel"]:
        is_admin_flag = 1 if is_admin(message.from_user.id) else 0
        await add_or_update_chat(
            chat_id=message.chat.id,
            title=message.chat.title or "Noma'lum",
            chat_type=chat_type,
            is_admin=is_admin_flag
        )

    if is_admin(message.from_user.id):
        await message.answer("👋 Salom Admin! Panelga xush kelibsiz.", reply_markup=main_menu_kb())
    else:
        text = (
            "👋 Salom!\n"
            "Bu bot guruhlarda xavfsizlikni ta’minlash uchun yaratilgan.\n\n"
            "📌 Asosiy vazifalari:\n"
            "• Yomon so‘zlarni filtrlash 🚫\n"
            "• Xavfli fayllarni o‘chirish 🦠\n"
            "• Qoidabuzarlarni vaqtincha bloklash 🔇\n\n"
            "👉 Botni guruhingizga qo‘shib, unga admin huquqlari bering."
        )
        add_button = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="➕ Guruhga qo‘shish",
                    url=f"https://t.me/{(await message.bot.me()).username}?startgroup=new"
                )],
                [InlineKeyboardButton(text="ℹ️ Bot qanday ishlaydi?", callback_data="help_info")]
            ]
        )
        await message.answer(text, reply_markup=add_button)


@router.callback_query(F.data == "help_info")
async def show_help(call: types.CallbackQuery):
    text = (
        "📖 <b>Qo‘llanma</b>\n\n"
        "1️⃣ Botni guruhingizga qo‘shing.\n"
        "2️⃣ Botga <b>admin huquqlarini</b> bering.\n"
        "3️⃣ Bot avtomatik ravishda:\n"
        "   • Yomon so‘zlarni o‘chiradi 🚫\n"
        "   • Xavfli fayllarni bloklaydi 🦠\n"
        "   • Qoidabuzarlarni vaqtincha bloklaydi 🔇\n\n"
        "✅ Shu tariqa guruhingiz xavfsiz bo‘ladi!"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=back_to_main_kb())
    await call.answer()


# ================== MENU NAVIGATION ==================
@router.callback_query(F.data == "menu:main")
async def go_main_menu(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)

    # ❗ Eski funksiyalarni to‘xtatish uchun state tozalanadi
    await state.clear()

    await call.message.edit_text("🔘 Asosiy menyu", reply_markup=main_menu_kb())
    await call.answer()


# ================== FALLBACK MESSAGE HANDLER (no state) ==================
@router.message(F.text)
async def fallback_message(message: types.Message, state: FSMContext):
    # Faqat adminlar uchun
    if not is_admin(message.from_user.id):
        return

    # Agar admin hech qanday state ichida bo‘lmasa
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❗ Iltimos, menyudan kerakli tugmani tanlang.", 
                             reply_markup=main_menu_kb())


# ================== STATISTICS / EXPORT ==================
@router.callback_query(F.data == "stats")
async def statistics_handler(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    chats = await get_all_chats()
    total = len(chats)
    admins = sum(1 for c in chats if c[3] == 1)
    normals = total - admins
    text = f"📊 Statistikalar:\n\n👥 Umumiy: {total}\n🛡 Admin bo‘lgan: {admins}\n👤 Oddiy: {normals}"
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "export:txt")
async def export_txt_handler(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    chats = await get_all_chats()
    file_path = export_chats_to_txt(chats)
    await call.message.answer_document(types.FSInputFile(file_path))
    await call.answer("✅ TXT tayyor")


@router.callback_query(F.data == "export:pdf")
async def export_pdf_handler(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    chats = await get_all_chats()
    file_path = export_chats_to_pdf(chats)
    await call.message.answer_document(types.FSInputFile(file_path))
    await call.answer("✅ PDF tayyor")


# ================== MEDIA BROADCAST ==================
@router.callback_query(F.data == "media:start")
async def ask_media_post(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    await state.set_state(MediaState.waiting_media)
    await call.message.edit_text(
        "🖼 Rasm/🎬 Video/🎞 GIF/📎 Fayl yuboring.\nCaption ichida HTML linklar ishlatish mumkin.",
        reply_markup=back_to_main_kb()
    )
    await call.answer()


@router.message(MediaState.waiting_media, F.content_type.in_({"photo","video","animation","document"}))
async def broadcast_media_post(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    chats = await get_all_chats()
    count = 0
    caption = msg.html_text or None
    for chat in chats:
        try:
            if msg.photo:
                await msg.bot.send_photo(chat[0], msg.photo[-1].file_id, caption=caption)
            elif msg.video:
                await msg.bot.send_video(chat[0], msg.video.file_id, caption=caption)
            elif msg.animation:
                await msg.bot.send_animation(chat[0], msg.animation.file_id, caption=caption)
            elif msg.document:
                await msg.bot.send_document(chat[0], msg.document.file_id, caption=caption)
            else:
                continue
            count += 1
            await asyncio.sleep(0.06)
        except Exception:
            continue
    await msg.answer(f"✅ Media post {count} chatga yuborildi.")
    await state.clear()


# ================== CHAT MEMBER TRACKING ==================
@router.my_chat_member()
async def chat_member_handler(event: types.ChatMemberUpdated):
    chat = event.chat
    status = event.new_chat_member.status
    is_admin_flag = 1 if status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR] else 0
    if chat.type in ["group", "supergroup", "channel"]:
        await add_or_update_chat(chat.id, chat.title or "Noma'lum", chat.type, is_admin_flag)


# ================== FILE SAFETY FILTER ==================
@router.message(F.content_type == "document")
async def remove_unsafe_files(message: types.Message):
    doc = message.document
    name = (doc.file_name or "").lower()

    # Guruhga xos whitelist tekshiruvi
    if await is_whitelisted(message.chat.id, message.from_user.id):
        return  # ruxsat berilgan bo‘lsa fayl o‘chirilmadi

    if any(name.endswith(ext) for ext in UNSAFE_EXT):
        try:
            await message.delete()
            info_msg = await message.answer(f"❌ {name} fayli o‘chirildi (xavfsizlik).")
            await asyncio.sleep(2)
            await info_msg.delete()
        except Exception:
            pass


# ================== BAD WORDS FILTER (GROUPS) ==================
@router.message(F.text & (F.chat.type.in_({"group", "supergroup"})))
async def bad_words_guard(message: types.Message):
    # Adminni cheklamaymiz
    if message.from_user and is_admin(message.from_user.id):
        return

    txt = (message.text or message.caption or "").lower()
    if not txt:
        return

    words = await list_bad_words(message.chat.id)  # chatga xos + global
    if not words:
        return

    # Word-boundary qidiruv (diakritika-safely)
    pattern = r"(?<!\\w)(" + "|".join(re.escape(w) for w in words) + r")(?!\\w)"
    if re.search(pattern, txt, flags=re.IGNORECASE):
        try:
            await message.delete()
        except Exception:
            pass

        # Mute
        minutes = await get_mute_minutes(message.chat.id)
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        perms = ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_add_web_page_previews=False
        )
        try:
            await message.bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                permissions=perms,
                until_date=until
            )
            warn = await message.answer(
                f"🚫 <a href='tg://user?id={message.from_user.id}'>Foydalanuvchi</a> {minutes} daqiqaga mute qilindi.",
                parse_mode="HTML"
            )
            await asyncio.sleep(5)
            await warn.delete()
        except Exception:
            pass

# ================== BAD WORDS ==================
@router.callback_query(F.data == "bw:menu")
async def bad_words_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ So‘z qo‘shish", callback_data="bw:add")],
        [InlineKeyboardButton(text="➖ So‘z o‘chirish", callback_data="bw:remove")],
        [InlineKeyboardButton(text="📃 Ro‘yxat (global)", callback_data="bw:list:g"),
         InlineKeyboardButton(text="📃 Ro‘yxat (chat)", callback_data="bw:list:c")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")]
    ])
    await call.message.edit_text("🛡 Yomon so‘zlar boshqaruvi:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "bw:add")
async def bw_add_prompt(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BadWordStates.add_words)
    await call.message.edit_text("So‘z(lar)ni vergul bilan ajratib yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(BadWordStates.add_words, F.text)
async def bw_add_take(m: types.Message, state: FSMContext):
    txt = (m.text or "").strip()

    # Super admin -> global so'z
    if is_admin(m.from_user.id):
        target_chat = None
    else:
        # Oddiy foydalanuvchi faqat guruh ichida admin bo'lsa qo'sha oladi
        if m.chat.type not in ["group", "supergroup"]:
            await m.answer("❌ Siz faqat guruh ichida so‘z qo‘shishingiz mumkin.")
            await state.clear()
            return

        member = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await m.answer("⛔ Siz guruh admini emassiz.")
            await state.clear()
            return

        target_chat = m.chat.id

    items = [w.strip() for w in txt.split(",") if w.strip()]
    for w in items:
        await add_bad_word(w, target_chat)

    await m.answer(
        f"✅ {len(items)} ta so‘z qo‘shildi. (target: {'global' if target_chat is None else 'chat'})",
        reply_markup=back_to_main_kb()
    )
    await state.clear()


@router.callback_query(F.data == "bw:remove")
async def bw_remove_prompt(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(BadWordStates.remove_words)
    await call.message.edit_text("O‘chirmoqchi bo‘lgan so‘z(lar)ni yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(BadWordStates.remove_words, F.text)
async def bw_remove_take(m: types.Message, state: FSMContext):
    txt = (m.text or "").strip()

    # Super admin -> global
    if is_admin(m.from_user.id):
        target_chat = None
    else:
        if m.chat.type not in ["group", "supergroup"]:
            await m.answer("❌ Siz faqat guruh ichida so‘z o‘chira olasiz.")
            await state.clear()
            return

        member = await m.bot.get_chat_member(m.chat.id, m.from_user.id)
        if member.status not in ["administrator", "creator"]:
            await m.answer("⛔ Siz guruh admini emassiz.")
            await state.clear()
            return

        target_chat = m.chat.id

    items = [w.strip().lower() for w in txt.split(",") if w.strip()]
    for w in items:
        await remove_bad_word(w, target_chat)

    await m.answer(
        f"🗑 {len(items)} ta so‘z o‘chirildi. (target: {'global' if target_chat is None else 'chat'})",
        reply_markup=back_to_main_kb()
    )
    await state.clear()


@router.callback_query(F.data == "bw:list:g")
async def list_global_words(call: types.CallbackQuery):
    words = await list_bad_words(None)
    text = "Global ro‘yxat bo‘sh." if not words else ("Global so‘zlar:\n- " + "\n- ".join(words))
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "bw:list:c")
async def list_chat_words(call: types.CallbackQuery):
    cid = call.message.chat.id if call.message.chat.type in ["group", "supergroup"] else None
    words = await list_bad_words(cid)
    text = (
        "Bu chat uchun ro‘yxat bo‘sh (global so‘zlar bo‘lishi mumkin)."
        if not words else ("Chat so‘zlari (global bilan birga):\n- " + "\n- ".join(words))
    )
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


# ================== MUTE DURATION ==================
CHATS_PER_PAGE = 10

@router.callback_query(F.data == "mute:menu")
async def ask_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    await state.set_state(MuteStates.choose_chat)
    await show_chat_page(call, state, page=0)

    # chats = await get_all_chats()
    # if not chats:
    #     await call.message.edit_text("Bot hech qaysi guruhda yo‘q.", reply_markup=back_to_main_kb())
    #     return await call.answer()
    # kb = InlineKeyboardMarkup(inline_keyboard=[
    #     [InlineKeyboardButton(text=title or str(chat_id), callback_data=f"mute:chat:{chat_id}")]
    #     for chat_id, title, *_ in chats
    # ] + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")]])
    # await state.set_state(MuteStates.choose_chat)
    # await call.message.edit_text("Qaysi guruh uchun mute vaqtini o‘rnatmoqchisiz?", reply_markup=kb)
    # await call.answer()


async def show_chat_page(call: types.CallbackQuery, state: FSMContext, page: int):
    chats = await get_all_chats()
    if not chats:
        await call.message.edit_text("Bot hech qaysi guruhda yo‘q.", reply_markup=back_to_main_kb())
        return
    total = len(chats)
    start = page * CHATS_PER_PAGE
    end = start + CHATS_PER_PAGE
    page_chats = chats[start:end]

    kb_rows = [
        [InlineKeyboardButton(text=title or str(chat_id), callback_data=f"mute:chat:{chat_id}")]
        for chat_id, title, *_ in page_chats
    ]

    # Navigatsiya tugmalari
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"mute:page:{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"mute:page:{page+1}"))
    if nav:
        kb_rows.append(nav)

    # Asosiy menyuga qaytish tugmasi
    kb_rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await call.message.edit_text("Qaysi guruh uchun mute vaqtini o‘rnatmoqchisiz?", reply_markup=kb)


@router.callback_query(F.data.startswith("mute:page:"), MuteStates.choose_chat)
async def paginate_chats(call: types.CallbackQuery, state: FSMContext):
    page = int(call.data.split(":")[2])
    await show_chat_page(call, state, page)
    await call.answer()


@router.callback_query(F.data.startswith("mute:chat:"), MuteStates.choose_chat)
async def choose_chat(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[2])
    await state.update_data(chat_id=chat_id)
    current = await get_mute_minutes(chat_id)
    await state.set_state(MuteStates.enter_minutes)
    await callback.message.edit_text(
        f"🔹 Guruh ID: {chat_id}\nJoriy mute davomiyligi: {current} daqiqa.\n"
        f"Yangi qiymatni yuboring (1–4320 daqiqa):",
        reply_markup=back_to_main_kb()
    )
    await callback.answer()


# ✅ Regexni to‘g‘riladik
@router.message(MuteStates.enter_minutes, F.text.regexp(r"^\d{1,4}$"))
async def set_mute_duration(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    chat_id = int(data.get("chat_id"))
    minutes = int(message.text.strip())

    # (ixtiyoriy) 1–4320 oralig‘ida tekshirib qo‘yamiz
    if not (1 <= minutes <= 4320):
        return await message.answer("❗ 1–4320 oralig‘ida raqam yuboring.", reply_markup=back_to_main_kb())

    await set_mute_minutes(chat_id, minutes)
    new_value = await get_mute_minutes(chat_id)

    await message.answer(
        f"✅ Guruh ID {chat_id} uchun mute davomiyligi {new_value} daqiqa qilib saqlandi.",
        reply_markup=back_to_main_kb()
    )
    await state.clear()


# ❌ Noto‘g‘ri kiritmalarni holat ichida ushlash (foydali)
@router.message(MuteStates.enter_minutes)
async def set_mute_duration_bad_input(message: types.Message, state: FSMContext):
    await message.answer("❗ Faqat raqam yuboring (1–4320). Yoki ⬅️ Orqaga bosing.",
                         reply_markup=back_to_main_kb())



# ================== USERS LIST (PAGINATION) ==================
async def show_users_page(target_message: types.Message | types.CallbackQuery, page: int):
    users = await get_all_users()
    if not users:
        text = "👥 Hozircha foydalanuvchilar yo‘q."
        if isinstance(target_message, types.CallbackQuery):
            await target_message.message.edit_text(text, reply_markup=back_to_main_kb())
        else:
            await target_message.answer(text, reply_markup=back_to_main_kb())
        return

    total = len(users)
    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    page_users = users[start:end]

    text = f"👥 Foydalanuvchilar (jami: {total})\n\n"

    kb_rows = []
    for u in page_users:
        name = f"{u[1] or ''} {u[2] or ''}".strip() or "—"
        btn_text = f"{name} ({u[0]})"
        kb_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"user:detail:{u[0]}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"users:page:{page-1}"))
    if end < total:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"users:page:{page+1}"))
    if nav_buttons:
        kb_rows.append(nav_buttons)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if isinstance(target_message, types.CallbackQuery):
        await target_message.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await target_message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("users:page:"))
async def users_pagination(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    page = int(call.data.split(":")[2])
    await show_users_page(call, page)
    await call.answer()


@router.callback_query(F.data.startswith("user:detail:"))
async def user_detail(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    user = await get_user_by_id(user_id)
    if not user:
        await call.answer("❌ Bunday foydalanuvchi topilmadi.", show_alert=True)
        return

    text = (
        f"📄 <b>Foydalanuvchi tafsilotlari</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"👤 Ism: {user[1] or '—'}\n"
        f"👤 Familiya: {user[2] or '—'}\n"
        f"📛 Username: {('@' + user[3]) if user[3] else '—'}\n"
        f"🌐 Til: {user[4] or '—'}\n"
        f"📅 Qo‘shilgan: {user[5] or '—'}\n"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="users:page:0")]
    ])

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# ================== WHITELIST ==================
@router.callback_query(F.data == "wh:menu")
async def whitelist_menu(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Foydalanuvchi qo‘shish", callback_data="wh:add:choose_chat")],
        [InlineKeyboardButton(text="➖ Foydalanuvchini o‘chirish", callback_data="wh:rem:choose_chat")],
        [InlineKeyboardButton(text="📃 Ruxsatli foydalanuvchilar", callback_data="wh:list")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")]
    ])
    await call.message.edit_text("Fayl yuborish ruxsatlarini boshqarish:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "wh:add:choose_chat")
async def wh_add_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    chats = await get_all_chats()
    if not chats:
        await call.message.edit_text("Bot hech qaysi guruhda yo‘q.", reply_markup=back_to_main_kb())
        return await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=title or str(chat_id), callback_data=f"wh:add:chat:{chat_id}")]
        for chat_id, title, *_ in chats
    ] + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="wh:menu")]])
    await state.set_state(WhitelistStates.add_choose_chat)
    await call.message.edit_text("Qaysi guruhga foydalanuvchi qo‘shiladi?", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("wh:add:chat:"), WhitelistStates.add_choose_chat)
async def wh_add_got_chat(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[3])
    await state.update_data(chat_id=chat_id)
    await state.set_state(WhitelistStates.add_enter_user)
    await callback.message.edit_text("Foydalanuvchi ID raqamini yuboring (raqam ko‘rinishida).",
                                    reply_markup=back_to_main_kb())
    await callback.answer()


@router.message(WhitelistStates.add_enter_user, F.text.regexp(r"^\d+$"))
async def wh_add_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    chat_id = data.get("chat_id")
    user_id = int(message.text.strip())
    await add_whitelist_user(chat_id, user_id)
    await message.answer(f"✅ {user_id} foydalanuvchiga fayl tashlashga ruxsat berildi (chat_id={chat_id}).",
                         reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:rem:choose_chat")
async def wh_rem_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    chats = await get_all_chats()
    if not chats:
        await call.message.edit_text("Bot hech qaysi guruhda yo‘q.", reply_markup=back_to_main_kb())
        return await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=title or str(chat_id), callback_data=f"wh:rem:chat:{chat_id}")]
        for chat_id, title, *_ in chats
    ] + [[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="wh:menu")]])
    await state.set_state(WhitelistStates.rem_choose_chat)
    await call.message.edit_text("Qaysi guruhdan foydalanuvchini o‘chirasiz?", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("wh:rem:chat:"), WhitelistStates.rem_choose_chat)
async def wh_rem_got_chat(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[3])
    await state.update_data(chat_id=chat_id)
    await state.set_state(WhitelistStates.rem_enter_user)
    await callback.message.edit_text("O‘chirmoqchi bo‘lgan foydalanuvchi ID raqamini yuboring.",
                                    reply_markup=back_to_main_kb())
    await callback.answer()


@router.message(WhitelistStates.rem_enter_user, F.text.regexp(r"^\d+$"))
async def wh_remove_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    chat_id = data.get("chat_id")
    user_id = int(message.text.strip())
    await remove_whitelist_user(chat_id, user_id)
    await message.answer(f"🗑 {user_id} foydalanuvchidan fayl yuborish ruxsati olib tashlandi (chat_id={chat_id}).",
                         reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:list")
async def wh_list_all(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)

    chats = await get_all_chats()
    if not chats:
        await call.message.edit_text("Bot hech qaysi guruhda yo‘q.", reply_markup=back_to_main_kb())
        return await call.answer()

    text = "📃 Guruhlar bo‘yicha oq ro‘yxat:\n\n"
    for chat_id, title, *_ in chats:
        users = await list_whitelist(chat_id)
        if users:
            text += f"🔹 {title} ({chat_id}):\n"
            for u in users:
                try:
                    member = await call.message.bot.get_chat_member(chat_id, u)
                    name = member.user.full_name
                    uname = f"@{member.user.username}" if member.user.username else ""
                    text += f"   - {name} {uname} (ID: {u})\n"
                except Exception:
                    text += f"   - (ID: {u}) [foydalanuvchini olish imkoni yo‘q]\n"
            text += "\n"
    if text.strip() == "📃 Guruhlar bo‘yicha oq ro‘yxat:":
        await call.message.edit_text("📃 Hech bir guruhda ruxsatli foydalanuvchi yo‘q.", reply_markup=back_to_main_kb())
    else:
        await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


# ================== FALLBACK BACK BUTTON (message) ==================
@router.message(F.text == "⬅️ Orqaga")
async def back_to_main_message(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔘 Asosiy menyu", reply_markup=main_menu_kb())

