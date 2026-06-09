import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from aiogram import Router, types, F
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_ID
from database import (
    add_bad_word,
    add_or_update_chat,
    add_or_update_user,
    add_security_log,
    add_unsafe_extension,
    create_referral_link,
    add_warning,
    add_whitelist_user,
    get_all_chats,
    get_all_users,
    get_chat_count,
    get_mute_minutes,
    get_referral_chats,
    get_referral_stats,
    get_security_logs,
    get_settings,
    get_user_by_id,
    is_whitelisted,
    list_bad_words,
    list_unsafe_extensions,
    list_whitelist,
    remove_bad_word,
    remove_unsafe_extension,
    remove_unsafe_all_extensions,
    track_referral_chat,
    remove_whitelist_user,
    reset_warning,
    set_mute_minutes,
    update_setting,
)
from utils.file_export import export_chats_to_pdf, export_chats_to_txt

logger = logging.getLogger(__name__)
router = Router()

USERS_PER_PAGE = 10
CHATS_PER_PAGE = 10
REF_LINKS_PER_PAGE = 10
REF_GROUPS_PER_PAGE = 10


class BadWordStates(StatesGroup):
    add_words = State()
    remove_words = State()


class MuteStates(StatesGroup):
    choose_chat = State()
    enter_minutes = State()


class WhitelistStates(StatesGroup):
    add_choose_chat = State()
    add_enter_user = State()
    rem_choose_chat = State()
    rem_enter_user = State()


class ExtStates(StatesGroup):
    add_ext = State()
    remove_ext = State()
    remove_all = State()


class SettingStates(StatesGroup):
    choose_chat = State()
    enter_value = State()


class MediaState(StatesGroup):
    waiting_media = State()


class ReferralStates(StatesGroup):
    enter_name = State()


def is_super_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in ADMIN_ID)


async def is_group_admin(message_or_call) -> bool:
    chat = message_or_call.chat if isinstance(message_or_call, types.Message) else message_or_call.message.chat
    user = message_or_call.from_user
    if not user:
        return False
    if is_super_admin(user.id):
        return True
    if chat.type not in {"group", "supergroup"}:
        return False
    try:
        member = await message_or_call.bot.get_chat_member(chat.id, user.id)
        return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
    except Exception:
        return False


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="stats"),
            InlineKeyboardButton(text="🧾 Oxirgi loglar", callback_data="logs"),
        ],
        [
            InlineKeyboardButton(text="🛡 Yomon so‘zlar", callback_data="bw:menu"),
            InlineKeyboardButton(text="🦠 Xavfli fayllar", callback_data="ext:menu"),
        ],
        [
            InlineKeyboardButton(text="⏱ Mute va sozlamalar", callback_data="settings:menu"),
            InlineKeyboardButton(text="✅ Oq ro‘yxat", callback_data="wh:menu"),
        ],
        [
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="users:page:0"),
            InlineKeyboardButton(text="🖼 Ommaviy xabar", callback_data="media:start"),
        ],
        [
            InlineKeyboardButton(text="🔗 Giper ssilkalar", callback_data="ref:menu"),
        ],
        [
            InlineKeyboardButton(text="📄 TXT eksport", callback_data="export:txt"),
            InlineKeyboardButton(text="📑 PDF eksport", callback_data="export:pdf"),
        ],
    ])


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")]
    ])


def back_to_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Sozlamalarga qaytish", callback_data="settings:menu")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")],
    ])


def public_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=f"https://t.me/{bot_username}?startgroup=new")],
        [InlineKeyboardButton(text="ℹ️ Qo‘llanma", callback_data="help_info")],
    ])


def short_name(user: types.User | None) -> str:
    if not user:
        return "Noma’lum"
    name = user.full_name or "Foydalanuvchi"
    if user.username:
        return f"{name} (@{user.username})"
    return name


def normalize_items(text: str) -> list[str]:
    return [x.strip().lower() for x in re.split(r"[,\n]+", text or "") if x.strip()]


def get_document_ext(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def has_double_extension(filename: str) -> bool:
    parts = Path(filename or "").name.lower().split(".")
    return len(parts) >= 3 and ("." + parts[-2]) in {
        ".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".txt"
    }


def is_archive(filename: str) -> bool:
    return get_document_ext(filename) in {".zip", ".rar", ".7z", ".tar", ".gz"}


def contains_bad_word(text: str, words: list[str]) -> bool:
    if not text or not words:
        return False
    # Katta ro‘yxatda ham xavfsiz ishlashi uchun eng uzun so‘zlardan boshlaymiz.
    words = sorted({w.strip().lower() for w in words if w.strip()}, key=len, reverse=True)
    pattern = r"(?<![\w'])(" + "|".join(re.escape(w) for w in words) + r")(?![\w'])"
    return bool(re.search(pattern, text.lower(), flags=re.IGNORECASE | re.UNICODE))


async def delete_later(message: types.Message, seconds: int = 5):
    await asyncio.sleep(seconds)
    try:
        await message.delete()
    except Exception:
        pass


async def mute_user(bot, chat_id: int, user_id: int, minutes: int):
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
        can_add_web_page_previews=False,
    )
    await bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=perms, until_date=until)


async def choose_chat_keyboard(prefix: str, page: int = 0) -> InlineKeyboardMarkup:
    chats = await get_all_chats()
    start = page * CHATS_PER_PAGE
    end = start + CHATS_PER_PAGE
    rows = [
        [InlineKeyboardButton(text=(title or str(chat_id))[:60], callback_data=f"{prefix}:chat:{chat_id}")]
        for chat_id, title, *_ in chats[start:end]
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:page:{page-1}"))
    if end < len(chats):
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"{prefix}:page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_chat_link(chat: types.Chat):
    if chat.username:
        return f"https://t.me/{chat.username}"
    return None


@router.message(Command("start", "panel"))
async def start_handler(message: types.Message, command: CommandObject):
    await add_or_update_user(message.from_user)

    if message.chat.type in {"group", "supergroup", "channel"}:
        try:
            bot_member = await message.bot.get_chat_member(message.chat.id, (await message.bot.me()).id)
            is_bot_admin = 1 if bot_member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} else 0
        except Exception:
            is_bot_admin = 0

        await add_or_update_chat(
            message.chat.id,
            message.chat.title or "Noma’lum",
            message.chat.type,
            await get_chat_link(message.chat),
            is_bot_admin
        )

        payload = (command.args or "").strip() if command else ""
        if payload.startswith("ref_"):
            await track_referral_chat(payload, message.chat.id)

        await message.answer("✅ Xavfsizlik boti guruhda ishlayapti. Botga xabarlarni o‘chirish va foydalanuvchini cheklash huquqini bering.")
        return

    if is_super_admin(message.from_user.id):
        await message.answer("👋 <b>Admin panel</b>\nKerakli bo‘limni tanlang:", reply_markup=main_menu_kb())
        return

    bot_username = (await message.bot.me()).username
    await message.answer(
        "👋 <b>Salom!</b>\n\n"
        "Men guruhingizni xavfsizroq qilishga yordam beraman:\n"
        "• yomon so‘zlarni o‘chiraman;\n"
        "• xavfli fayllarni bloklayman;\n"
        "• qoidabuzarlarga ogohlantirish berib, kerak bo‘lsa vaqtincha mute qilaman.\n\n"
        "Botni guruhga qo‘shing va admin huquqini bering.",
        reply_markup=public_kb(bot_username)
    )




def referral_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi giper ssilka", callback_data="ref:create")],
        [InlineKeyboardButton(text="📊 Ssilka statistikasi", callback_data="ref:list")],
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")],
    ])


@router.callback_query(F.data == "ref:menu")
async def referral_menu(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    await state.clear()
    await call.message.edit_text(
        "🔗 <b>Giper ssilkalar</b>\n\n"
        "Bu yerda botni guruhlarga qo‘shish uchun cheksiz havola yaratish va har bir havola statistikalarini ko‘rish mumkin.",
        reply_markup=referral_menu_kb()
    )
    await call.answer()


@router.callback_query(F.data == "ref:create")
async def referral_create_start(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    await state.set_state(ReferralStates.enter_name)
    await call.message.edit_text("Yangi ssilka nomini yuboring. Masalan: <b>Instagram reklama</b>", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(ReferralStates.enter_name)
async def referral_create_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return

    name = (message.text or "").strip()[:100] or "Nomsiz havola"
    code = "ref_" + secrets.token_urlsafe(6).replace("-", "_")
    await create_referral_link(name, code, message.from_user.id)

    bot_username = (await message.bot.me()).username
    url = (
        f"https://t.me/{bot_username}?startgroup={code}"
        "&admin=delete_messages+restrict_members"
    )

    await message.answer(
        "✅ <b>Yangi giper ssilka yaratildi</b>\n\n"
        f"🏷 Nomi: <b>{escape(name)}</b>\n"
        f"🔗 Havola:\n<code>{escape(url)}</code>\n\n"
        "Bu havola orqali bot guruhga qo‘shilganda statistika avtomatik hisoblanadi.",
        reply_markup=referral_menu_kb()
    )
    await state.clear()


@router.callback_query(F.data.startswith("ref:list"))
async def referral_list(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)

    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    rows = await get_referral_stats()
    total = len(rows)
    if not rows:
        await call.message.edit_text("🔗 Hozircha ssilka yaratilmagan.", reply_markup=referral_menu_kb())
        return await call.answer()

    max_page = max((total - 1) // REF_LINKS_PER_PAGE, 0)
    page = max(0, min(page, max_page))
    start = page * REF_LINKS_PER_PAGE
    end = start + REF_LINKS_PER_PAGE
    page_rows = rows[start:end]

    bot_username = (await call.bot.me()).username
    text = (
        "📊 <b>Giper ssilkalar statistikasi</b>\n"
        f"Sahifa: <b>{page + 1}/{max_page + 1}</b> | Jami ssilkalar: <b>{total}</b>\n\n"
    )
    kb_rows = []

    for number, (link_id, name, code, groups_count, admin_count, created_at) in enumerate(page_rows, start=start + 1):
        url = f"https://t.me/{bot_username}?startgroup={code}&admin=delete_messages+restrict_members"
        text += (
            f"{number}. 🔹 <b>{escape(name)}</b>\n"
            f"👥 Qo‘shilgan guruhlar: <b>{groups_count}</b>\n"
            f"🛡 Admin qilinganlar: <b>{admin_count}</b>\n"
            f"🔗 <code>{escape(url)}</code>\n\n"
        )
        kb_rows.append([InlineKeyboardButton(
            text=f"📄 {number}. {name[:30]} ({groups_count})",
            callback_data=f"ref:detail:{link_id}:0:{page}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ref:list:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"ref:list:{page + 1}"))
    if nav:
        kb_rows.append(nav)

    kb_rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ref:menu")])
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("ref:detail:"))
async def referral_detail(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)

    parts = call.data.split(":")
    link_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    back_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0

    stats_rows = await get_referral_stats()
    current_link = next((row for row in stats_rows if row[0] == link_id), None)
    chats = await get_referral_chats(link_id)
    total = len(chats)

    max_page = max((total - 1) // REF_GROUPS_PER_PAGE, 0)
    page = max(0, min(page, max_page))
    start = page * REF_GROUPS_PER_PAGE
    end = start + REF_GROUPS_PER_PAGE
    page_chats = chats[start:end]

    if current_link:
        _, link_name, _, groups_count, admin_count, _ = current_link
        text = (
            f"📄 <b>{escape(link_name)}</b> orqali qo‘shilgan guruhlar\n"
            f"Sahifa: <b>{page + 1}/{max_page + 1}</b> | "
            f"Jami: <b>{groups_count}</b> | Admin: <b>{admin_count}</b>\n\n"
        )
    else:
        text = "📄 <b>Ssilka orqali qo‘shilgan guruhlar</b>\n\n"

    if not chats:
        text += "Bu ssilka orqali hali guruh qo‘shilmagan."
    else:
        for number, (chat_id, title, chat_type, is_admin, added_at) in enumerate(page_chats, start=start + 1):
            status = "🛡 admin" if is_admin else "⚠️ admin emas"
            text += (
                f"{number}. <b>{escape(title or str(chat_id))}</b>\n"
                f"ID: <code>{chat_id}</code> | {status}\n\n"

            )

    kb_rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ref:detail:{link_id}:{page - 1}:{back_page}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"ref:detail:{link_id}:{page + 1}:{back_page}"))
    if nav:
        kb_rows.append(nav)

    kb_rows.append([InlineKeyboardButton(text="⬅️ Statistikaga qaytish", callback_data=f"ref:list:{back_page}")])
    kb_rows.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")])

    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()

@router.callback_query(F.data == "help_info")
async def show_help(call: types.CallbackQuery):
    await call.message.edit_text(
        "📖 <b>Qo‘llanma</b>\n\n"
        "1️⃣ Botni guruhga qo‘shing.\n"
        "2️⃣ Botga quyidagi admin huquqlarini bering: xabarlarni o‘chirish, foydalanuvchini cheklash.\n"
        "3️⃣ Admin panel orqali yomon so‘zlar, xavfli fayl kengaytmalari, mute va oq ro‘yxatni sozlang.\n\n"
        "✅ Shundan keyin bot guruhni avtomatik nazorat qiladi.",
        reply_markup=back_to_main_kb()
    )
    await call.answer()


@router.callback_query(F.data == "menu:main")
async def go_main_menu(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    await state.clear()
    await call.message.edit_text("🏠 <b>Asosiy menyu</b>", reply_markup=main_menu_kb())
    await call.answer()


@router.my_chat_member()
async def chat_member_handler(event: types.ChatMemberUpdated):
    chat = event.chat
    status = event.new_chat_member.status
    if chat.type in {"group", "supergroup", "channel"}:
        is_admin_flag = 1 if status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} else 0
        await add_or_update_chat(chat.id, chat.title or "Noma’lum", chat.type, await get_chat_link(chat), is_admin_flag)


@router.message(F.new_chat_members)
async def save_new_members(message: types.Message):
    for user in message.new_chat_members or []:
        if not user.is_bot:
            await add_or_update_user(user)


@router.message(F.left_chat_member)
async def service_left_member(message: types.Message):
    settings = await get_settings(message.chat.id)
    if settings["delete_service_messages"]:
        try:
            await message.delete()
        except Exception:
            pass


@router.callback_query(F.data == "stats")
async def statistics_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    chats = await get_all_chats()
    users = await get_all_users()
    bot_admin_chats = sum(1 for c in chats if c[4] == 1)
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Guruh/kanallar: <b>{len(chats)}</b>\n"
        f"🛡 Bot admin bo‘lgan chatlar: <b>{bot_admin_chats}</b>\n"
        f"👤 Saqlangan foydalanuvchilar: <b>{len(users)}</b>\n"
        f"🦠 Global xavfli kengaytmalar: <b>{len(await list_unsafe_extensions(None))}</b>\n"
        f"🚫 Global yomon so‘zlar: <b>{len(await list_bad_words(None))}</b>"
    )
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "logs")
async def logs_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    rows = await get_security_logs(20)
    if not rows:
        text = "🧾 Hozircha loglar yo‘q."
    else:
        text = "🧾 <b>Oxirgi xavfsizlik loglari</b>\n\n"
        for chat_id, user_id, action, reason, file_name, created_at in rows:
            text += (
                f"• <b>{escape(action)}</b> — {escape(reason or '—')}\n"
                f"  Chat: <code>{chat_id}</code> | User: <code>{user_id}</code>\n"
                f"  Fayl: {escape(file_name or '—')} | {created_at}\n\n"
            )
    await call.message.edit_text(text[:3900], reply_markup=back_to_main_kb())
    await call.answer()



@router.callback_query(F.data == "export:txt")
async def export_txt_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    chats = await get_all_chats()
    print(chats)
    file_path = export_chats_to_txt(chats)
    await call.message.answer_document(types.FSInputFile(file_path))
    await call.answer("✅ TXT tayyor")


@router.callback_query(F.data == "export:pdf")
async def export_pdf_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    chats = await get_all_chats()
    print(chats)
    file_path = export_chats_to_pdf(chats)
    await call.message.answer_document(types.FSInputFile(file_path))
    await call.answer("✅ PDF tayyor")


@router.callback_query(F.data == "bw:menu")
async def bad_words_menu(call: types.CallbackQuery):
    if not await is_group_admin(call):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ So‘z qo‘shish", callback_data="bw:add")],
        [InlineKeyboardButton(text="➖ So‘z o‘chirish", callback_data="bw:remove")],
        [
            InlineKeyboardButton(text="📃 Global ro‘yxat", callback_data="bw:list:g"),
            InlineKeyboardButton(text="📃 Chat ro‘yxati", callback_data="bw:list:c"),
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")],
    ])
    await call.message.edit_text("🛡 <b>Yomon so‘zlar boshqaruvi</b>", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "bw:add")
async def bw_add_prompt(call: types.CallbackQuery, state: FSMContext):
    if not await is_group_admin(call):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    await state.set_state(BadWordStates.add_words)
    await call.message.edit_text("Qo‘shiladigan so‘zlarni vergul yoki yangi qatorda yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(BadWordStates.add_words, F.text)
async def bw_add_take(message: types.Message, state: FSMContext):
    if not await is_group_admin(message):
        return
    target_chat = None if is_super_admin(message.from_user.id) and message.chat.type == "private" else message.chat.id
    items = normalize_items(message.text)
    added = 0
    for word in items:
        if await add_bad_word(word, target_chat):
            added += 1
    await message.answer(f"✅ {added} ta so‘z qo‘shildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "bw:remove")
async def bw_remove_prompt(call: types.CallbackQuery, state: FSMContext):
    if not await is_group_admin(call):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    await state.set_state(BadWordStates.remove_words)
    await call.message.edit_text("O‘chiriladigan so‘zlarni vergul yoki yangi qatorda yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(BadWordStates.remove_words, F.text)
async def bw_remove_take(message: types.Message, state: FSMContext):
    if not await is_group_admin(message):
        return
    target_chat = None if is_super_admin(message.from_user.id) and message.chat.type == "private" else message.chat.id
    removed = 0
    for word in normalize_items(message.text):
        if await remove_bad_word(word, target_chat):
            removed += 1
    await message.answer(f"🗑 {removed} ta so‘z o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data.in_({"bw:list:g", "bw:list:c"}))
async def list_words(call: types.CallbackQuery):
    if not await is_group_admin(call):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    chat_id = None if call.data == "bw:list:g" else call.message.chat.id
    words = await list_bad_words(chat_id)
    title = "Global yomon so‘zlar" if chat_id is None else "Ushbu chatdagi yomon so‘zlar"
    text = f"📃 <b>{title}</b>\n\n" + ("\n".join(f"• {escape(w)}" for w in words) if words else "Ro‘yxat bo‘sh.")
    await call.message.edit_text(text[:3900], reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "ext:menu")
async def ext_menu(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kengaytma qo‘shish", callback_data="ext:add")],
        [InlineKeyboardButton(text="➖ Kengaytma o‘chirish", callback_data="ext:remove")],
        [InlineKeyboardButton(text="🗑 Barchasini o‘chirish", callback_data="ext:remove_all")],
        [InlineKeyboardButton(text="📃 Ro‘yxat", callback_data="ext:list")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")],
    ])
    await call.message.edit_text("🦠 <b>Xavfli fayl kengaytmalari</b>", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "ext:add")
async def ext_add_prompt(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return
    await state.set_state(ExtStates.add_ext)
    await call.message.edit_text("Qo‘shiladigan kengaytmalarni yuboring. Masalan: <code>.exe, .apk, .js</code>", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(ExtStates.add_ext, F.text)
async def ext_add_take(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    for ext in normalize_items(message.text):
        await add_unsafe_extension(ext, None)
    await message.answer("✅ Kengaytmalar qo‘shildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "ext:remove")
async def ext_remove_prompt(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return
    await state.set_state(ExtStates.remove_ext)
    await call.message.edit_text("O‘chiriladigan kengaytmalarni yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(ExtStates.remove_ext, F.text)
async def ext_remove_take(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    for ext in normalize_items(message.text):
        await remove_unsafe_extension(ext, None)
    await message.answer("🗑 Kengaytmalar o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "ext:remove_all")
async def ext_remove_all(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return
    await remove_unsafe_all_extensions(None)
    await call.message.answer("🗑 Barcha xavfli kengaytmalar o‘chirildi.", reply_markup=back_to_main_kb())
    await call.answer()

@router.callback_query(ExtStates.remove_all, F.data == "ext:remove_all")
async def ext_remove_all_confirm(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return
    await remove_unsafe_all_extensions(None)
    await call.message.answer("🗑 Barcha xavfli kengaytmalar o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "ext:list")
async def ext_list(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return
    exts = await list_unsafe_extensions(None)
    text = "🦠 <b>Xavfli kengaytmalar</b>\n\n" + ("\n".join(f"• <code>{escape(e)}</code>" for e in exts) if exts else "Ro‘yxat bo‘sh.")
    await call.message.edit_text(text[:3900], reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "settings:menu")
async def settings_menu(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ Mute vaqti", callback_data="set:mute_minutes")],
        [InlineKeyboardButton(text="⚠️ Ogohlantirish limiti", callback_data="set:max_warnings")],
        [InlineKeyboardButton(text="📦 Maksimal fayl MB", callback_data="set:max_file_mb")],
        [InlineKeyboardButton(text="📁 Arxivlarni bloklash", callback_data="set:block_archives")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")],
    ])
    await call.message.edit_text("⚙️ <b>Guruh sozlamalari</b>\nAvval sozlama turini tanlang.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("set:"))
async def setting_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return
    key = call.data.split(":", 1)[1]
    await state.update_data(setting_key=key)
    await state.set_state(SettingStates.choose_chat)
    await call.message.edit_text("Qaysi guruh uchun sozlama o‘zgartiriladi?", reply_markup=await choose_chat_keyboard("setting", 0))
    await call.answer()


@router.callback_query(F.data.startswith("setting:page:"), SettingStates.choose_chat)
async def setting_page(call: types.CallbackQuery):
    page = int(call.data.split(":")[2])
    await call.message.edit_reply_markup(reply_markup=await choose_chat_keyboard("setting", page))
    await call.answer()


@router.callback_query(F.data.startswith("setting:chat:"), SettingStates.choose_chat)
async def setting_chat_selected(call: types.CallbackQuery, state: FSMContext):
    chat_id = int(call.data.split(":")[2])
    data = await state.get_data()
    key = data["setting_key"]
    await state.update_data(chat_id=chat_id)
    settings = await get_settings(chat_id)
    labels = {
        "mute_minutes": "Mute vaqti daqiqada",
        "max_warnings": "Ogohlantirish limiti",
        "max_file_mb": "Maksimal fayl hajmi MB",
        "block_archives": "Arxivlarni bloklash: 1 = ha, 0 = yo‘q",
    }
    await state.set_state(SettingStates.enter_value)
    await call.message.edit_text(
        f"Joriy qiymat: <code>{settings[key]}</code>\n\n{labels[key]} uchun yangi qiymat yuboring.",
        reply_markup=back_to_settings_kb()
    )
    await call.answer()


@router.message(SettingStates.enter_value, F.text.regexp(r"^\d{1,5}$"))
async def setting_save(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("setting_key")
    chat_id = int(data.get("chat_id"))
    value = int(message.text)
    ranges = {
        "mute_minutes": (1, 4320),
        "max_warnings": (1, 20),
        "max_file_mb": (1, 2000),
        "block_archives": (0, 1),
    }
    lo, hi = ranges[key]
    if not lo <= value <= hi:
        return await message.answer(f"❗ Qiymat {lo}–{hi} oralig‘ida bo‘lishi kerak.")
    await update_setting(chat_id, key, value)
    await message.answer("✅ Sozlama saqlandi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:menu")
async def whitelist_menu(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Foydalanuvchi qo‘shish", callback_data="wh:add:choose_chat")],
        [InlineKeyboardButton(text="➖ Foydalanuvchini o‘chirish", callback_data="wh:rem:choose_chat")],
        [InlineKeyboardButton(text="📃 Oq ro‘yxat", callback_data="wh:list")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")],
    ])
    await call.message.edit_text("✅ <b>Oq ro‘yxat</b>\nBu ro‘yxatdagi foydalanuvchilarning fayllari bloklanmaydi.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "wh:add:choose_chat")
async def wh_add_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return
    await state.set_state(WhitelistStates.add_choose_chat)
    await call.message.edit_text("Qaysi guruhga foydalanuvchi qo‘shiladi?", reply_markup=await choose_chat_keyboard("whadd", 0))
    await call.answer()


@router.callback_query(F.data.startswith("whadd:chat:"), WhitelistStates.add_choose_chat)
async def wh_add_got_chat(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(chat_id=int(call.data.split(":")[2]))
    await state.set_state(WhitelistStates.add_enter_user)
    await call.message.edit_text("Foydalanuvchi ID raqamini yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(WhitelistStates.add_enter_user, F.text.regexp(r"^\d+$"))
async def wh_add_user(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = int(message.text)
    await add_whitelist_user(int(data["chat_id"]), user_id)
    await message.answer(f"✅ <code>{user_id}</code> oq ro‘yxatga qo‘shildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:rem:choose_chat")
async def wh_rem_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return
    await state.set_state(WhitelistStates.rem_choose_chat)
    await call.message.edit_text("Qaysi guruhdan foydalanuvchi o‘chiriladi?", reply_markup=await choose_chat_keyboard("whrem", 0))
    await call.answer()


@router.callback_query(F.data.startswith("whrem:chat:"), WhitelistStates.rem_choose_chat)
async def wh_rem_got_chat(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(chat_id=int(call.data.split(":")[2]))
    await state.set_state(WhitelistStates.rem_enter_user)
    await call.message.edit_text("O‘chiriladigan foydalanuvchi ID raqamini yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(WhitelistStates.rem_enter_user, F.text.regexp(r"^\d+$"))
async def wh_remove_user(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = int(message.text)
    await remove_whitelist_user(int(data["chat_id"]), user_id)
    await message.answer(f"🗑 <code>{user_id}</code> oq ro‘yxatdan o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:list")
async def wh_list_all(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return
    chats = await get_all_chats()
    text = "📃 <b>Guruhlar bo‘yicha oq ro‘yxat</b>\n\n"
    found = False
    for chat_id, title, *_ in chats:
        users = await list_whitelist(chat_id)
        if not users:
            continue
        found = True
        text += f"🔹 {escape(title or str(chat_id))} — <code>{chat_id}</code>\n"
        text += "\n".join(f"   • <code>{u}</code>" for u in users) + "\n\n"
    if not found:
        text += "Hozircha ruxsatli foydalanuvchi yo‘q."
    await call.message.edit_text(text[:3900], reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "media:start")
async def ask_media_post(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    await state.set_state(MediaState.waiting_media)
    await call.message.edit_text("Yuboriladigan xabarni, rasmni, videoni yoki faylni yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(MediaState.waiting_media)
async def broadcast_media_post(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    chats = await get_all_chats()
    sent = 0
    failed = 0
    for chat_id, *_ in chats:
        try:
            await message.copy_to(chat_id)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await message.answer(f"✅ Xabar yuborildi: {sent} ta\n❌ Xato: {failed} ta", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data.startswith("users:page:"))
async def users_pagination(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Sizga ruxsat yo‘q.", show_alert=True)
    page = int(call.data.split(":")[2])
    users = await get_all_users()
    if not users:
        return await call.message.edit_text("👥 Hozircha foydalanuvchilar yo‘q.", reply_markup=back_to_main_kb())
    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    rows = []
    for u in users[start:end]:
        name = f"{u[1] or ''} {u[2] or ''}".strip() or "Noma’lum"
        rows.append([InlineKeyboardButton(text=f"{name} ({u[0]})", callback_data=f"user:detail:{u[0]}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"users:page:{page-1}"))
    if end < len(users):
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"users:page:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])
    await call.message.edit_text(f"👥 <b>Foydalanuvchilar</b>\nJami: <b>{len(users)}</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("user:detail:"))
async def user_detail(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return
    user_id = int(call.data.split(":")[2])
    user = await get_user_by_id(user_id)
    if not user:
        return await call.answer("❌ Topilmadi.", show_alert=True)
    text = (
        "📄 <b>Foydalanuvchi tafsilotlari</b>\n\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"👤 Ism: {escape(user[1] or '—')}\n"
        f"👤 Familiya: {escape(user[2] or '—')}\n"
        f"📛 Username: {('@' + escape(user[3])) if user[3] else '—'}\n"
        f"🌐 Til: {escape(user[4] or '—')}\n"
        f"📅 Qo‘shilgan: {escape(user[5] or '—')}"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="users:page:0")]
    ]))
    await call.answer()


@router.message(F.content_type == "document")
async def remove_unsafe_files(message: types.Message):
    if message.chat.type not in {"group", "supergroup"} or not message.from_user or not message.document:
        return

    await add_or_update_user(message.from_user)

    if await is_group_admin(message):
        return
    if await is_whitelisted(message.chat.id, message.from_user.id):
        return

    doc = message.document
    filename = doc.file_name or "nomalum_fayl"
    lower_name = filename.lower()
    ext = get_document_ext(lower_name)
    settings = await get_settings(message.chat.id)
    unsafe_exts = set(await list_unsafe_extensions(message.chat.id))

    reason = None
    if ext in unsafe_exts:
        reason = f"xavfli kengaytma: {ext}"
    elif has_double_extension(lower_name):
        reason = "ikki martalik kengaytma"
    elif settings["block_archives"] and is_archive(lower_name):
        reason = "arxiv fayl bloklangan"
    elif doc.file_size and doc.file_size > settings["max_file_mb"] * 1024 * 1024:
        reason = f"fayl hajmi {settings['max_file_mb']} MB dan katta"

    if not reason:
        return

    try:
        await message.delete()
    except Exception:
        pass

    await add_security_log(message.chat.id, message.from_user.id, "Fayl o‘chirildi", reason, filename)
    warn_count = await add_warning(message.chat.id, message.from_user.id)

    text = (
        f"🦠 <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.full_name)}</a>, "
        f"faylingiz o‘chirildi.\n"
        f"Sabab: <b>{escape(reason)}</b>\n"
        f"Ogohlantirish: <b>{warn_count}/{settings['max_warnings']}</b>"
    )

    if warn_count >= settings["max_warnings"]:
        try:
            await mute_user(message.bot, message.chat.id, message.from_user.id, settings["mute_minutes"])
            await reset_warning(message.chat.id, message.from_user.id)
            text += f"\n🔇 Limit oshgani uchun {settings['mute_minutes']} daqiqaga yozish cheklovi qo‘yildi."
            await add_security_log(message.chat.id, message.from_user.id, "Mute", "fayl ogohlantirish limiti", filename)
        except Exception as exc:
            logger.exception("Mute xatosi: %s", exc)

    info = await message.answer(text)
    asyncio.create_task(delete_later(info, 10))


@router.message((F.text | F.caption) & (F.chat.type.in_({"group", "supergroup"})))
async def bad_words_guard(message: types.Message):
    if not message.from_user:
        return

    await add_or_update_user(message.from_user)

    if await is_group_admin(message):
        return

    text = message.text or message.caption or ""
    words = await list_bad_words(message.chat.id)
    if not contains_bad_word(text, words):
        return

    settings = await get_settings(message.chat.id)

    try:
        await message.delete()
    except Exception:
        pass

    warn_count = await add_warning(message.chat.id, message.from_user.id)
    await add_security_log(message.chat.id, message.from_user.id, "Xabar o‘chirildi", "yomon so‘z", "")

    warn_text = (
        f"🚫 <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.full_name)}</a>, "
        f"guruh qoidalariga zid so‘z ishlatildi.\n"
        f"Ogohlantirish: <b>{warn_count}/{settings['max_warnings']}</b>"
    )

    if warn_count >= settings["max_warnings"]:
        try:
            await mute_user(message.bot, message.chat.id, message.from_user.id, settings["mute_minutes"])
            await reset_warning(message.chat.id, message.from_user.id)
            warn_text += f"\n🔇 {settings['mute_minutes']} daqiqaga yozish cheklovi qo‘yildi."
            await add_security_log(message.chat.id, message.from_user.id, "Mute", "yomon so‘z limiti", "")
        except Exception as exc:
            logger.exception("Mute xatosi: %s", exc)

    warn = await message.answer(warn_text)
    asyncio.create_task(delete_later(warn, 10))


@router.message()
async def collect_users_and_chats(message: types.Message):
    if message.from_user:
        await add_or_update_user(message.from_user)
    if message.chat.type in {"group", "supergroup", "channel"}:
        await add_or_update_chat(message.chat.id, message.chat.title or "Noma’lum", message.chat.type, await get_chat_link(message.chat), 0)
