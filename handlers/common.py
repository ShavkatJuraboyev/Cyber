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
    add_panel_admin,
    remove_panel_admin,
    list_panel_admins,
    get_panel_admin,
    set_panel_admin_permission,
    get_panel_admin_permissions,
    panel_admin_has_permission,
    create_panel_role,
    update_panel_role,
    delete_panel_role,
    list_panel_roles,
    get_panel_role,
    set_panel_role_permission,
    get_panel_role_permissions,
    assign_role_to_admin,
    remove_role_from_admin,
    get_admin_roles,
    get_admin_effective_permissions,
    panel_admin_has_effective_permission,
    add_bad_word,
    add_or_update_chat,
    add_or_update_user,
    delete_chat,
    add_security_log,
    add_unsafe_extension,
    create_referral_link,
    get_referral_link_by_id,
    update_referral_link_name,
    delete_referral_link,
    add_warning,
    add_whitelist_user,
    get_all_chats,
    get_all_users,
    get_user_count,
    get_chat_count,
    get_mute_minutes,
    get_referral_chats,
    get_referral_stats,
    get_chats_without_referral,
    assign_chat_to_referral,
    get_security_logs,
    get_security_log_count,
    get_settings,
    get_global_settings,
    get_user_by_id,
    is_whitelisted,
    list_bad_words,
    list_unsafe_extensions,
    list_whitelist,
    remove_bad_word,
    remove_unsafe_extension,
    remove_unsafe_all_extensions,
    track_referral_chat,
    save_user_referral_click,
    get_user_referral_click,
    track_referral_chat_by_user,
    remove_whitelist_user,
    reset_warning,
    set_mute_minutes,
    update_chat_bot_status,
    update_setting,
    update_setting_for_all_chats,
    set_panel_admin_expiry,
    disable_expired_panel_admins,
    add_admin_audit_log,
    get_admin_audit_logs,
    set_private_log_chat_id,
    get_private_log_chat_id,
    get_stats_summary,
    get_stats_summary_cached,
    get_chat_by_id,
    get_referral_chat_count,
)
from utils.file_export import export_chats_to_pdf, export_chats_to_txt, export_referral_chats_to_pdf, export_referral_chats_to_txt

logger = logging.getLogger(__name__)


async def safe_edit_text(message: types.Message, text: str, reply_markup=None, **kwargs):
    """edit_text ishlamasa bot yiqilmasin: eski/o‘chgan xabarda yangi xabar yuboradi."""
    try:
        return await message.edit_text(text, reply_markup=reply_markup, **kwargs)
    except TelegramBadRequest as exc:
        err = str(exc).lower()
        if "message is not modified" in err:
            return None
        if "message to edit not found" in err or "message can't be edited" in err or "message identifier is not specified" in err:
            return await message.answer(text, reply_markup=reply_markup, **kwargs)
        raise

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
    choose_target = State()
    waiting_media = State()


class ReferralStates(StatesGroup):
    enter_name = State()
    edit_name = State()


class PanelAdminStates(StatesGroup):
    add_admin = State()
    create_role = State()
    edit_role_name = State()
    set_expiry = State()


class PublicQuizStates(StatesGroup):
    answer = State()


PANEL_MODULES = {
    "stats": "📊 Statistika",
    "chats": "📋 Guruh/kanallar",
    "logs": "🧾 Loglar",
    "referrals": "🔗 Giper ssilkalar",
    "users": "👥 Foydalanuvchilar",
    "bad_words": "🛡 Yomon so‘zlar",
    "extensions": "🦠 Xavfli fayllar",
    "settings": "⏱ Sozlamalar",
    "whitelist": "✅ Oq ro‘yxat",
    "broadcast": "🖼 Ommaviy xabar",
    "exports": "📄 Eksport",
    "admins": "👮 Adminlar/rollar",
    "secret_logs": "🔐 Maxfiy guruh",
}

CRUD_ACTIONS = {
    "read": "👁 Ko‘rish",
    "create": "➕ Qo‘shish",
    "update": "✏️ Tahrirlash",
    "delete": "🗑 O‘chirish",
    "action": "⚙️ Amal bajarish",
}

PANEL_PERMISSIONS = {
    f"{module}.{action}": f"{label} — {action_label}"
    for module, label in PANEL_MODULES.items()
    for action, action_label in CRUD_ACTIONS.items()
}


ROLE_TEMPLATES = {
    "read_only": {"name": "Read only", "perms": [f"{m}.read" for m in PANEL_MODULES]},
    "moderator": {"name": "Moderator", "perms": ["stats.read", "logs.read", "bad_words.read", "bad_words.create", "bad_words.delete", "extensions.read", "extensions.create", "extensions.delete", "whitelist.read", "whitelist.create", "whitelist.delete"]},
    "referral_manager": {"name": "Referral manager", "perms": ["referrals.read", "referrals.create", "referrals.update", "referrals.delete", "chats.read", "stats.read"]},
    "security_admin": {"name": "Security admin", "perms": ["stats.read", "logs.read", "chats.read", "bad_words.read", "bad_words.create", "bad_words.update", "bad_words.delete", "extensions.read", "extensions.create", "extensions.update", "extensions.delete", "settings.read", "settings.update", "whitelist.read", "whitelist.create", "whitelist.delete", "secret_logs.read", "secret_logs.update"]},
}


def confirm_kb(confirm_data: str, cancel_data: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data=confirm_data)],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=cancel_data)],
    ])


def format_permission_preview(perms: set[str]) -> str:
    if not perms:
        return "⛔ Hech qanday huquq yo‘q."
    lines = []
    for module, label in PANEL_MODULES.items():
        acts = [CRUD_ACTIONS[a] for a in CRUD_ACTIONS if f"{module}.{a}" in perms or f"{module}.*" in perms]
        if acts:
            lines.append(f"• <b>{escape(label)}</b>: " + ", ".join(escape(a) for a in acts))
    return "\n".join(lines) if lines else "⛔ Hech qanday huquq yo‘q."


def module_has_any(perms: set[str], module: str) -> bool:
    return f"{module}.*" in perms or any(p.startswith(f"{module}.") for p in perms)


def can_perm(perms: set[str], permission: str) -> bool:
    module = permission.split(".", 1)[0]
    return permission in perms or f"{module}.*" in perms

def can_read(perms: set[str], module: str) -> bool:
    return can_perm(perms, f"{module}.read")

def can_create(perms: set[str], module: str) -> bool:
    return can_perm(perms, f"{module}.create")

def can_update(perms: set[str], module: str) -> bool:
    return can_perm(perms, f"{module}.update")

def can_delete(perms: set[str], module: str) -> bool:
    return can_perm(perms, f"{module}.delete")

def can_action(perms: set[str], module: str) -> bool:
    return can_perm(perms, f"{module}.action")


def is_super_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id in ADMIN_ID)


async def has_panel_access(user_id: int | None, permission: str | None = None) -> bool:
    if not user_id:
        return False
    if is_super_admin(user_id):
        return True
    await disable_expired_panel_admins()
    admin = await get_panel_admin(user_id)
    if not admin or int(admin[3]) != 1:
        return False
    if permission is None:
        return True
    # Yangi CRUD permission: module.action. Eski chaqiruvlar kelib qolsa, module.read deb tekshiramiz.
    if "." not in permission:
        perms = await get_admin_effective_permissions(user_id)
        return module_has_any(perms, permission) or permission in perms
    return await panel_admin_has_effective_permission(user_id, permission)




async def demote_panel_admin_if_empty(user_id: int) -> bool:
    """Adminning barcha effective huquqlari tugasa, uni oddiy foydalanuvchiga aylantiradi."""
    if is_super_admin(user_id):
        return False

    perms = await get_admin_effective_permissions(user_id)
    if perms:
        return False

    await remove_panel_admin(user_id)
    return True


async def deny_if_no_permission(call: types.CallbackQuery, permission: str | None = None) -> bool:
    if await has_panel_access(call.from_user.id, permission):
        return False
    await call.answer("⛔ Sizga bu bo‘lim uchun ruxsat berilmagan.", show_alert=True)
    return True


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
            InlineKeyboardButton(text="👮 Adminlar", callback_data="pa:menu"),
        ],
        [
            InlineKeyboardButton(text="📄 TXT eksport", callback_data="export:txt"),
            InlineKeyboardButton(text="📑 PDF eksport", callback_data="export:pdf"),
        ],
        [InlineKeyboardButton(text="🔐 Maxfiy guruh", callback_data="secret:menu")],
    ])


async def panel_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    if is_super_admin(user_id):
        return main_menu_kb()

    perms = await get_admin_effective_permissions(user_id)
    rows = []
    if module_has_any(perms, "stats"):
        rows.append([InlineKeyboardButton(text="📊 Statistika", callback_data="stats")])
    if module_has_any(perms, "logs"):
        rows.append([InlineKeyboardButton(text="🧾 Oxirgi loglar", callback_data="logs")])
    if module_has_any(perms, "bad_words"):
        rows.append([InlineKeyboardButton(text="🛡 Yomon so‘zlar", callback_data="bw:menu")])
    if module_has_any(perms, "extensions"):
        rows.append([InlineKeyboardButton(text="🦠 Xavfli fayllar", callback_data="ext:menu")])
    if module_has_any(perms, "settings"):
        rows.append([InlineKeyboardButton(text="⏱ Mute va sozlamalar", callback_data="settings:menu")])
    if module_has_any(perms, "whitelist"):
        rows.append([InlineKeyboardButton(text="✅ Oq ro‘yxat", callback_data="wh:menu")])
    if module_has_any(perms, "users"):
        rows.append([InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="users:page:0")])
    if module_has_any(perms, "broadcast"):
        rows.append([InlineKeyboardButton(text="🖼 Ommaviy xabar", callback_data="media:start")])
    if module_has_any(perms, "referrals"):
        rows.append([InlineKeyboardButton(text="🔗 Giper ssilkalar", callback_data="ref:menu")])
    if module_has_any(perms, "exports"):
        rows.append([
            InlineKeyboardButton(text="📄 TXT eksport", callback_data="export:txt"),
            InlineKeyboardButton(text="📑 PDF eksport", callback_data="export:pdf"),
        ])
    if module_has_any(perms, "secret_logs"):
        rows.append([InlineKeyboardButton(text="🔐 Maxfiy guruh", callback_data="secret:menu")])
    if not rows:
        rows.append([InlineKeyboardButton(text="⛔ Ruxsat berilmagan", callback_data="noop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")]
    ])


def stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Umumiy statistikani ko‘rish", callback_data="stats")],
        [InlineKeyboardButton(text="📋 Guruh/kanallar ro‘yxati", callback_data="chats:page:0")],
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")],
    ])

def back_to_settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Sozlamalarga qaytish", callback_data="settings:menu")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")],
    ])


def public_kb(bot_username: str) -> InlineKeyboardMarkup:
    rights = "delete_messages+restrict_members+invite_users+pin_messages"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=f"https://t.me/{bot_username}?startgroup=new&admin={rights}")],
        [InlineKeyboardButton(text="📢 Kanalga qo‘shish", url=f"https://t.me/{bot_username}?startchannel=new&admin={rights}")],
        [InlineKeyboardButton(text="📖 Qo‘llanma", callback_data="help_info"), InlineKeyboardButton(text="🧪 Demo", callback_data="demo_info")],
        [InlineKeyboardButton(text="🛡 Xavfsizlik testi", callback_data="security_quiz"), InlineKeyboardButton(text="❓ FAQ", callback_data="faq_info")],
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
    rows = []
    if prefix == "setting" and page == 0:
        rows.append([InlineKeyboardButton(text="🌐 Barcha guruh/kanallar uchun", callback_data=f"{prefix}:all")])
    rows.extend(
        [InlineKeyboardButton(text=(title or str(chat_id))[:60], callback_data=f"{prefix}:chat:{chat_id}")]
        for chat_id, title, *_ in chats[start:end]
    )
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


async def refresh_one_chat_status(bot, chat_id: int) -> tuple[int, str]:
    """Telegramdan botning real statusini tekshiradi va bazani yangilaydi."""
    try:
        bot_id = (await bot.me()).id
        member = await bot.get_chat_member(chat_id, bot_id)
        status = getattr(member.status, "value", str(member.status))
        is_admin = 1 if member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} else 0
        await update_chat_bot_status(chat_id, is_admin, status)
        return is_admin, status
    except (TelegramForbiddenError, TelegramBadRequest):
        # Bot guruh/kanaldan chiqarilgan, bloklangan yoki chat topilmadi.
        await update_chat_bot_status(chat_id, 0, "not_member")
        return 0, "not_member"
    except Exception as exc:
        logger.exception("Chat statusini tekshirishda xato. chat_id=%s: %s", chat_id, exc)
        await update_chat_bot_status(chat_id, 0, "unknown")
        return 0, "unknown"


async def refresh_all_chat_statuses(bot):
    """Barcha saqlangan guruh/kanallar statusini Telegramdan real-vaqtga yaqin yangilaydi.

    Tekshiruvlar parallel, lekin cheklangan holda bajariladi. Shu sabab 1000+ chat bo'lsa ham
    panel bitta-bitta kutib qotib qolmaydi va Telegram limitlariga ham ehtiyot bo'ladi.
    """
    chats = await get_all_chats()
    semaphore = asyncio.Semaphore(20)

    async def refresh_limited(chat_id: int):
        async with semaphore:
            return await refresh_one_chat_status(bot, chat_id)

    await asyncio.gather(*(refresh_limited(int(chat[0])) for chat in chats), return_exceptions=True)
    return await get_all_chats()


def render_bot_status(is_admin: int, bot_status: str | None = None) -> str:
    if bot_status in {"not_member", "left", "kicked"}:
        return "🚪 bot a’zo emas"
    if is_admin:
        return "🛡 admin"
    if bot_status in {"member", "restricted"}:
        return "👤 a’zo, admin emas"
    return "⚠️ admin emas"


