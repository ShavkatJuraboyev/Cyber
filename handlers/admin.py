from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatPermissions
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import html
from aiogram.exceptions import TelegramBadRequest
from config import ADMIN_ID
from database import (
    add_or_update_chat, get_all_chats,
    add_bad_word, remove_bad_word, list_bad_words,
    get_mute_minutes, set_mute_minutes, add_whitelist_user,
    remove_whitelist_user, list_whitelist, is_whitelisted
)
from utils.file_export import export_chats_to_txt, export_chats_to_pdf
import asyncio
import re
from datetime import timedelta, datetime, timezone

router = Router()
class WhitelistStates(StatesGroup):
    choose_chat_add = State()
    enter_user_add = State()
    choose_chat_remove = State()
    enter_user_remove = State()

class MuteStates(StatesGroup):
    choose_chat = State()
    enter_minutes = State()

# Foydali: xavfli ext ro‘yxati
UNSAFE_EXT = {".apk", ".js", ".bat", ".exe", ".scr", ".vbs", ".cmd", ".msi", ".reg", ".ps1"}

# ========= START =========
@router.message(Command("start"))
async def start_handler(message: types.Message):
    chat_type = message.chat.type  # 'private', 'group', 'supergroup', 'channel'

    # Faqat group va channel uchun bazaga qo‘shish
    if chat_type in ["group", "supergroup", "channel"]:
        # Eslatma: bu ADMIN_ID userga tegishli; guruh/kanda "bot" adminligi alohida
        is_admin = 1 if message.from_user and message.from_user.id in ADMIN_ID else 0
        await add_or_update_chat(
            chat_id=message.chat.id,
            title=message.chat.title or "Noma'lum",
            chat_type=chat_type,
            is_admin=is_admin
        )

    # Admin panel
    if message.from_user and message.from_user.id in ADMIN_ID:
        text = "👋 Salom Admin! Panelga xush kelibsiz."
        kb = [
            [types.KeyboardButton(text="📊 Statistikalar"),
             types.KeyboardButton(text="🛡 Fayl ruxsatlari")],
            [types.KeyboardButton(text="📄 TXT eksport"),
             types.KeyboardButton(text="📑 PDF eksport")],
            [types.KeyboardButton(text="📝 Matnli post"),
             types.KeyboardButton(text="🖼 Media post")],
            [types.KeyboardButton(text="🛡 Yomon so‘zlar"),
             types.KeyboardButton(text="⏱ Mute davomiyligi")],
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer("👋 Salom! Botimizga xush kelibsiz. Panel faqat admin uchun.")

# ========= STATISTIKA / EXPORT =========
@router.message(F.text == "📊 Statistikalar")
async def statistics_handler(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    chats = await get_all_chats()
    total = len(chats)
    admins = sum(1 for c in chats if c[3] == 1)
    normals = total - admins
    text = f"📊 Statistikalar:\n\n👥 Umumiy: {total}\n🛡 Admin bo‘lgan: {admins}\n👤 Oddiy: {normals}"
    await message.answer(text)

@router.message(F.text == "📄 TXT eksport")
async def export_txt_handler(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    chats = await get_all_chats()
    file_path = export_chats_to_txt(chats)
    await message.answer_document(types.FSInputFile(file_path))

@router.message(F.text == "📑 PDF eksport")
async def export_pdf_handler(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    chats = await get_all_chats()
    file_path = export_chats_to_pdf(chats)
    await message.answer_document(types.FSInputFile(file_path))

# ========= POST YUBORISH (MATN) =========
@router.message(F.text == "📝 Matnli post")
async def ask_text_post(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    await message.answer(
        "✍️ Post matnini yuboring (HTML ruxsat: <b>, <i>, <a href=\"...\">...</a>):",
        parse_mode=None  # ❗ HTML sifatida emas, oddiy matn sifatida yuboriladi
    )

    @router.message(lambda m: m.from_user and m.from_user.id in ADMIN_ID)
    async def broadcast_text_post(msg: types.Message):
        chats = await get_all_chats()
        count_html = 0
        count_plain = 0
        failed = []

        text_html = msg.html_text or msg.text or ""
        text_plain = html.escape(msg.text or "")

        for chat in chats:
            chat_id = chat[0]
            try:
                await msg.bot.send_message(
                    chat_id,
                    text_html,
                    disable_web_page_preview=False
                )
                count_html += 1
            except TelegramBadRequest:
                try:
                    await msg.bot.send_message(chat_id, text_plain)
                    count_plain += 1
                except Exception as e:
                    failed.append(chat_id)
            except Exception as e:
                failed.append(chat_id)

            await asyncio.sleep(0.05)

        summary = (
            f"✅ Matnli post yuborildi.\n"
            f"📌 HTML yuborildi: {count_html}\n"
            f"📌 Plain yuborildi: {count_plain}\n"
        )
        if failed:
            summary += f"❌ Xatolik bo‘lgan chatlar: {', '.join(map(str, failed))}"

        await msg.answer(summary)

        try:
            router.message_handlers.pop()
        except Exception:
            pass


# ========= POST YUBORISH (MEDIA) =========
@router.message(F.text == "🖼 Media post")
async def ask_media_post(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    await message.answer(
        "🖼 Rasm/🎬 Video/🎞 GIF (animation)/📎 Fayl yuboring.\n"
        "Caption ichida HTML linklar ishlatish mumkin."
    )

    @router.message(lambda m: m.from_user and m.from_user.id in ADMIN_ID and m.content_type in {"photo","video","animation","document"})
    async def broadcast_media_post(msg: types.Message):
        chats = await get_all_chats()
        count = 0

        caption = msg.html_text or None

        for chat in chats:
            try:
                if msg.photo:
                    file_id = msg.photo[-1].file_id
                    await msg.bot.send_photo(chat[0], file_id, caption=caption)
                elif msg.video:
                    await msg.bot.send_video(chat[0], msg.video.file_id, caption=caption)
                elif msg.animation:
                    await msg.bot.send_animation(chat[0], msg.animation.file_id, caption=caption)
                elif msg.document:
                    await msg.bot.send_document(chat[0], msg.document.file_id, caption=caption)
                else:
                    continue
                count += 1
                await asyncio.sleep(0.07)
            except Exception:
                continue

        await msg.answer(f"✅ Media post {count} chatga yuborildi.")
        try:
            router.message_handlers.pop()
        except Exception:
            pass

# ========= CHAT MEMBER KUZATUV =========
@router.my_chat_member()
async def chat_member_handler(event: types.ChatMemberUpdated):
    chat = event.chat
    status = event.new_chat_member.status
    is_admin = 1 if status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR] else 0
    if chat.type in ["group", "supergroup", "channel"]:
        await add_or_update_chat(chat.id, chat.title or "Noma'lum", chat.type, is_admin)

# ========= XAVFSIZ FAYLLARNI O‘CHIRISH =========
@router.message(F.content_type == "document")
async def remove_unsafe_files(message: types.Message):
    doc = message.document
    name = (doc.file_name or "").lower()

    # Guruhga xos whitelist tekshiruvi
    if await is_whitelisted(message.chat.id, message.from_user.id):
        return  # ✅ agar ruxsat berilgan bo‘lsa fayl o‘chirilmadi

    if any(name.endswith(ext) for ext in UNSAFE_EXT):
        try:
            await message.delete()
            info_msg = await message.answer(
                f"❌ {name} fayli o‘chirildi (xavfsizlik).")
            await asyncio.sleep(2)
            await info_msg.delete()
        except Exception:
            pass


# ========= YOMON SO‘Z FILTRI + TEMP MUTE =========
@router.message(F.text & (F.chat.type.in_({"group", "supergroup"})))
async def bad_words_guard(message: types.Message):
    # Adminning o‘zini cheklamaymiz
    if message.from_user and message.from_user.id in ADMIN_ID:
        return

    txt = (message.text or message.caption or "").lower()
    if not txt:
        return

    words = await list_bad_words(message.chat.id)   # chatga xos + global
    if not words:
        return

    # So‘z chegarasi bo‘yicha qidiramiz (word boundary). Diakritika/reg-ex safe.
    pattern = r"(?<!\w)(" + "|".join(re.escape(w) for w in words) + r")(?!\w)"
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
                f"🚫 <a href='tg://user?id={message.from_user.id}'>Foydalanuvchi</a> {minutes} daqiqaga mute qilindi."
            )
            await asyncio.sleep(5)
            await warn.delete()
        except Exception:
            pass

# ========= ADMIN: YOMON SO‘ZLARNI BOSHQARISH =========
@router.message(F.text == "🛡 Yomon so‘zlar")
async def bad_words_menu(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    kb = [
        [types.KeyboardButton(text="➕ So‘z qo‘shish"),
         types.KeyboardButton(text="➖ So‘z o‘chirish")],
        [types.KeyboardButton(text="📃 Ro‘yxat (global)"),
         types.KeyboardButton(text="📃 Ro‘yxat (chat)")],
        [types.KeyboardButton(text="⬅️ Orqaga")]
    ]
    await message.answer("Yomon so‘zlar boshqaruvi:", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))


@router.message(F.text == "➕ So‘z qo‘shish")
async def add_words_prompt(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    await message.answer("So‘z(lar)ni yuboring. Vergul bilan ajrating. Global uchun `global:` bilan boshlang. Masalan:\n`global: so'z1, so'z2`\n`so'z3, so'z4`")
    @router.message(lambda m: m.from_user and m.from_user.id in ADMIN_ID)
    async def add_words_take(m: types.Message):
        txt = (m.text or "").strip()
        target_chat = None
        if txt.lower().startswith("global:"):
            txt = txt.split(":", 1)[1]
            target_chat = None
        else:
            # Joriy chatga saqlash (private bo‘lsa globalga emas, shuning uchun None emas – lekin private chatda chat.id user bo‘ladi)
            target_chat = m.chat.id if m.chat.type in ["group","supergroup"] else None

        items = [w.strip() for w in txt.split(",") if w.strip()]
        for w in items:
            await add_bad_word(w, target_chat)
        await m.answer(f"✅ {len(items)} ta so‘z qo‘shildi. (target: {'global' if target_chat is None else 'chat'})")
        try:
            router.message_handlers.pop()
        except Exception:
            pass

@router.message(F.text == "➖ So‘z o‘chirish")
async def remove_words_prompt(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    await message.answer("O‘chirmoqchi bo‘lgan so‘z(lar)ni yuboring. `global:` bilan boshlasangiz globaldan o‘chiriladi.")
    @router.message(lambda m: m.from_user and m.from_user.id in ADMIN_ID)
    async def remove_words_take(m: types.Message):
        txt = (m.text or "").strip()
        target_chat = None
        if txt.lower().startswith("global:"):
            txt = txt.split(":", 1)[1]
            target_chat = None
        else:
            target_chat = m.chat.id if m.chat.type in ["group","supergroup"] else None

        items = [w.strip() for w in txt.split(",") if w.strip()]
        for w in items:
            await remove_bad_word(w, target_chat)
        await m.answer(f"🗑 {len(items)} ta so‘z o‘chirildi. (target: {'global' if target_chat is None else 'chat'})")
        try:
            router.message_handlers.pop()
        except Exception:
            pass

@router.message(F.text == "📃 Ro‘yxat (global)")
async def list_global_words(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    words = await list_bad_words(None)
    if not words:
        await message.answer("Global ro‘yxat bo‘sh.")
    else:
        await message.answer("Global so‘zlar:\n- " + "\n- ".join(words))

@router.message(F.text == "📃 Ro‘yxat (chat)")
async def list_chat_words(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    cid = message.chat.id if message.chat.type in ["group","supergroup"] else None
    words = await list_bad_words(cid)
    if not words:
        await message.answer("Bu chat uchun ro‘yxat bo‘sh (global so‘zlar bo‘lishi mumkin).")
    else:
        await message.answer("Chat so‘zlari (global bilan birga):\n- " + "\n- ".join(words))

@router.message(F.text == "⏱ Mute davomiyligi")
async def ask_choose_chat(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return
    
    chats = await get_all_chats()
    if not chats:
        await message.answer("Bot hech qaysi guruhda yo‘q.")
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=title, callback_data=f"mutechat:{chat_id}")]
        for chat_id, title, *_ in chats if title
    ])
    await state.set_state(MuteStates.choose_chat)
    await message.answer("Qaysi guruh uchun mute vaqtini o‘rnatmoqchisiz?", reply_markup=kb)


@router.callback_query(F.data.startswith("mutechat:"), MuteStates.choose_chat)
async def choose_chat(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)

    current = await get_mute_minutes(chat_id)
    await state.set_state(MuteStates.enter_minutes)
    await callback.message.edit_text(
        f"🔹 Guruh ID: {chat_id}\n"
        f"Joriy mute davomiyligi: {current} daqiqa.\n"
        f"Yangi qiymatni yuboring (1–4320 daqiqa):"
    )


@router.message(MuteStates.enter_minutes, F.text.regexp(r"^\d{1,4}$"))
async def set_mute_duration(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    minutes = int(message.text.strip())

    await set_mute_minutes(chat_id, minutes)
    await message.answer(
        f"✅ Guruh ID {chat_id} uchun mute davomiyligi {minutes} daqiqa qilib saqlandi."
    )
    await state.clear()


# ===== MENU =====
@router.message(F.text == "🛡 Fayl ruxsatlari")
async def whitelist_menu(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return
    kb = [
        [types.KeyboardButton(text="➕ Foydalanuvchi qo‘shish"),
         types.KeyboardButton(text="➖ Foydalanuvchini o‘chirish")],
        [types.KeyboardButton(text="📃 Ruxsatli foydalanuvchilar")],
        [types.KeyboardButton(text="⬅️ Orqaga")]
    ]
    await message.answer("Fayl yuborish ruxsatlarini boshqarish:",
        reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))


# ====== ADD USER FLOW ======
@router.message(F.text == "➕ Foydalanuvchi qo‘shish")
async def ask_choose_chat_add(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return
    chats = await get_all_chats()
    if not chats:
        await message.answer("Bot hech qaysi guruhda yo‘q.")
        return

    # inline tugmalar bilan ro‘yxat
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=title, callback_data=f"addchat:{chat_id}")]
        for chat_id, title, *_ in chats if title
    ])
    await state.set_state(WhitelistStates.choose_chat_add)
    await message.answer("Qaysi guruhga foydalanuvchi qo‘shiladi?", reply_markup=kb)


@router.callback_query(F.data.startswith("addchat:"), WhitelistStates.choose_chat_add)
async def choose_chat_add(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await state.set_state(WhitelistStates.enter_user_add)
    await callback.message.edit_text("Foydalanuvchi ID raqamini yuboring (raqam ko‘rinishida).")


@router.message(WhitelistStates.enter_user_add, F.text.regexp(r"^\d+$"))
async def add_to_whitelist(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    user_id = int(message.text.strip())
    await add_whitelist_user(chat_id, user_id)
    await message.answer(f"✅ {user_id} foydalanuvchiga fayl tashlashga ruxsat berildi (chat_id={chat_id}).")
    await state.clear()


# ====== REMOVE USER FLOW ======
@router.message(F.text == "➖ Foydalanuvchini o‘chirish")
async def ask_choose_chat_remove(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return
    chats = await get_all_chats()
    if not chats:
        await message.answer("Bot hech qaysi guruhda yo‘q.")
        return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=title, callback_data=f"remchat:{chat_id}")]
        for chat_id, title, *_ in chats if title
    ])
    await state.set_state(WhitelistStates.choose_chat_remove)
    await message.answer("Qaysi guruhdan foydalanuvchini o‘chirasiz?", reply_markup=kb)


@router.callback_query(F.data.startswith("remchat:"), WhitelistStates.choose_chat_remove)
async def choose_chat_remove(callback: types.CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[1])
    await state.update_data(chat_id=chat_id)
    await state.set_state(WhitelistStates.enter_user_remove)
    await callback.message.edit_text("O‘chirmoqchi bo‘lgan foydalanuvchi ID raqamini yuboring.")


@router.message(WhitelistStates.enter_user_remove, F.text.regexp(r"^\d+$"))
async def remove_from_whitelist(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("chat_id")
    user_id = int(message.text.strip())
    await remove_whitelist_user(chat_id, user_id)
    await message.answer(f"🗑 {user_id} foydalanuvchidan fayl yuborish ruxsati olib tashlandi (chat_id={chat_id}).")
    await state.clear()


# ====== LIST WHITELIST ======
@router.message(F.text == "📃 Ruxsatli foydalanuvchilar")
async def list_whitelisted(message: types.Message):
    if message.from_user.id not in ADMIN_ID:
        return

    chats = await get_all_chats()
    if not chats:
        await message.answer("Bot hech qaysi guruhda yo‘q.")
        return

    text = "📃 Guruhlar bo‘yicha oq ro‘yxat:\n\n"
    for chat_id, title, *_ in chats:
        users = await list_whitelist(chat_id)
        if users:
            text += f"🔹 {title} ({chat_id}):\n"
            for u in users:
                try:
                    member = await message.bot.get_chat_member(chat_id, u)
                    name = member.user.full_name
                    uname = f"@{member.user.username}" if member.user.username else ""
                    text += f"   - {name} {uname} (ID: {u})\n"
                except Exception:
                    text += f"   - (ID: {u}) [foydalanuvchini olish imkoni yo‘q]\n"
            text += "\n"

    if text.strip() == "📃 Guruhlar bo‘yicha oq ro‘yxat:":
        await message.answer("📃 Hech bir guruhda ruxsatli foydalanuvchi yo‘q.")
    else:
        await message.answer(text)




# Orqaga tugmasi
@router.message(F.text == "⬅️ Orqaga")
async def back_to_main(message: types.Message):
    await start_handler(message)
