from .common import *

router = Router()


@router.my_chat_member()
async def chat_member_handler(event: types.ChatMemberUpdated):
    chat = event.chat
    status = event.new_chat_member.status
    if chat.type in {"group", "supergroup", "channel"}:
        is_admin_flag = 1 if status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} else 0
        await add_or_update_chat(
            chat.id,
            chat.title or "Noma’lum",
            chat.type,
            await get_chat_link(chat),
            is_admin_flag,
            getattr(status, "value", str(status)),
        )

        # Referral tracking faqat bot admin qilinganda emas, bot chatga qo‘shilgan
        # har qanday holatda ishlashi kerak. Shunda admin panelda "qo‘shilgan" va
        # "admin qilingan" sonlari alohida ko‘rinadi.
        if event.from_user and status not in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
            await add_or_update_user(event.from_user)
            await track_referral_chat_by_user(event.from_user.id, chat.id)


@router.message(F.new_chat_members)
async def save_new_members(message: types.Message):
    for user in message.new_chat_members or []:
        if not user.is_bot:
            await add_or_update_user(user)


@router.message(F.left_chat_member)
async def service_left_member(message: types.Message):
    if message.chat.type not in {"group", "supergroup", "channel"}:
        return
    settings = await get_settings(message.chat.id)
    if settings["delete_service_messages"]:
        try:
            await message.delete()
        except Exception:
            pass


async def get_bot_delete_status(bot, chat_id: int) -> tuple[bool, str]:
    """Bot guruhdagi xabarlarni o‘chira olishini tekshiradi."""
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        status = member.status
        if status == ChatMemberStatus.CREATOR:
            return True, "creator"
        if status == ChatMemberStatus.ADMINISTRATOR and getattr(member, "can_delete_messages", False):
            return True, "administrator_can_delete"
        if status == ChatMemberStatus.ADMINISTRATOR:
            return False, "bot admin, lekin xabar o‘chirish huquqi yo‘q"
        return False, f"bot admin emas: {getattr(status, 'value', status)}"
    except Exception as exc:
        logger.exception("Bot delete huquqini tekshirishda xato: %s", exc)
        return False, "bot huquqini tekshirib bo‘lmadi"


def file_reason(doc: types.Document, filename: str, settings: dict, unsafe_exts: set[str]) -> str | None:
    """Oddiy va forward/pereslat qilingan document fayllarni bir xil tekshiradi."""
    lower_name = (filename or "").lower()
    ext = get_document_ext(lower_name)
    suffixes = {s.lower() for s in Path(lower_name).suffixes}

    # Agar fayl nomi image.jpg.exe kabi bo‘lsa, oxirgi kengaytma ham, barcha suffixlar ham tekshiriladi.
    if ext in unsafe_exts or suffixes.intersection(unsafe_exts):
        blocked = ext if ext in unsafe_exts else sorted(suffixes.intersection(unsafe_exts))[0]
        return f"xavfli kengaytma: {blocked}"
    if has_double_extension(lower_name):
        return "ikki martalik kengaytma"
    if settings["block_archives"] and is_archive(lower_name):
        return "arxiv fayl bloklangan"
    if doc.file_size and doc.file_size > settings["max_file_mb"] * 1024 * 1024:
        return f"fayl hajmi {settings['max_file_mb']} MB dan katta"
    return None


async def send_unsafe_file_to_secret_group(message: types.Message, reason: str, filename: str):
    private_log_chat_id = await get_private_log_chat_id()
    if not private_log_chat_id or not message.document:
        return

    sender_name = "Noma’lum"
    sender_line = "👤 Yuborgan: <b>Noma’lum</b>\n"
    if message.from_user:
        sender_name = message.from_user.full_name
        sender_line = (
            f"👤 Yuborgan: <a href='tg://user?id={message.from_user.id}'>{escape(sender_name)}</a>\n"
            f"🆔 User ID: <code>{message.from_user.id}</code>\n"
        )
    elif message.sender_chat:
        sender_line = (
            f"👤 Yuborgan: <b>{escape(message.sender_chat.title or str(message.sender_chat.id))}</b>\n"
            f"🆔 Sender chat ID: <code>{message.sender_chat.id}</code>\n"
        )

    caption = (
        "🦠 <b>Zararli fayl ushlandi</b>\n\n"
        f"👥 Guruh: <b>{escape(message.chat.title or str(message.chat.id))}</b>\n"
        f"🆔 Guruh ID: <code>{message.chat.id}</code>\n"
        f"{sender_line}"
        f"📄 Fayl: <code>{escape(filename)}</code>\n"
        f"⚠️ Sabab: <b>{escape(reason)}</b>"
    )

    try:
        await message.bot.send_document(
            private_log_chat_id,
            message.document.file_id,
            caption=caption,
            request_timeout=60,
        )
    except Exception as exc:
        logger.exception("Maxfiy guruhga fayl yuborishda xato: %s", exc)
        try:
            await message.bot.send_message(
                private_log_chat_id,
                caption + "\n\n⚠️ Faylni yuborishda network xatolik bo‘ldi, lekin guruhdagi zararli xabar o‘chirildi.",
                request_timeout=30,
            )
        except Exception as exc2:
            logger.exception("Maxfiy guruhga matnli log yuborishda xato: %s", exc2)


async def process_unsafe_document(message: types.Message):
    if message.chat.type not in {"group", "supergroup", "channel"} or not message.document:
        return

    if message.from_user:
        await add_or_update_user(message.from_user)
        # Faqat superadmin va whitelist o'tib ketsin. Oddiy guruh adminlari ham zararli fayl tashlasa bloklanadi.
        if is_super_admin(message.from_user.id):
            return
        if await is_whitelisted(message.chat.id, message.from_user.id):
            return

    doc = message.document
    filename = doc.file_name or "nomalum_fayl"
    settings = await get_settings(message.chat.id)
    unsafe_exts = set(await list_unsafe_extensions(message.chat.id))
    reason = file_reason(doc, filename, settings, unsafe_exts)

    if not reason:
        return

    can_delete, delete_status = await get_bot_delete_status(message.bot, message.chat.id)
    deleted = False
    if can_delete:
        try:
            await message.delete()
            deleted = True
        except Exception as exc:
            logger.exception("Zararli faylni guruhdan o‘chirishda xato: %s", exc)
            delete_status = "delete so‘rovida xato"
    else:
        logger.warning("Zararli fayl topildi, lekin bot o‘chira olmadi: %s", delete_status)

    await send_unsafe_file_to_secret_group(message, reason, filename)

    user_id = message.from_user.id if message.from_user else 0
    await add_security_log(
        message.chat.id,
        user_id,
        "Fayl o‘chirildi" if deleted else "Faylni o‘chirishda xato",
        reason if deleted else f"{reason}; {delete_status}",
        filename,
    )

    if not message.from_user:
        return

    warn_count = await add_warning(message.chat.id, message.from_user.id)
    text = (
        f"🦠 <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.full_name)}</a>, "
        f"faylingiz xavfsizlik sababli {'o‘chirildi' if deleted else 'ushlandi, lekin botda o‘chirish huquqi yo‘q'}.\n"
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

    try:
        info = await message.answer(text)
        asyncio.create_task(delete_later(info, 10))
    except Exception:
        pass


@router.message(F.document & F.chat.type.in_({"group", "supergroup"}))
async def remove_unsafe_files(message: types.Message):
    await process_unsafe_document(message)


@router.channel_post(F.document)
async def remove_unsafe_channel_files(message: types.Message):
    # Kanal postlarida from_user bo‘lmaydi, lekin document baribir tekshiriladi va o‘chiriladi.
    await process_unsafe_document(message)

@router.message((F.text | F.caption) & (F.chat.type.in_({"group", "supergroup"})))
async def bad_words_guard(message: types.Message):
    if not message.from_user:
        return

    await add_or_update_user(message.from_user)

    if is_super_admin(message.from_user.id):
        return
    if await is_whitelisted(message.chat.id, message.from_user.id):
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

    try:
        warn = await message.answer(warn_text)
        asyncio.create_task(delete_later(warn, 10))
    except Exception:
        pass


@router.message()
async def collect_users_and_chats(message: types.Message):
    if message.from_user:
        await add_or_update_user(message.from_user)
    if message.chat.type in {"group", "supergroup", "channel"}:
        await add_or_update_chat(
            message.chat.id,
            message.chat.title or "Noma’lum",
            message.chat.type,
            await get_chat_link(message.chat),
            None,
            None,
        )
