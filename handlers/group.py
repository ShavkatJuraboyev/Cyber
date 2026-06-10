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


@router.message(F.new_chat_members)
async def save_new_members(message: types.Message):
    for user in message.new_chat_members or []:
        if not user.is_bot:
            await add_or_update_user(user)


@router.message(F.left_chat_member)
async def service_left_member(message: types.Message):
    if message.chat.type not in {"group", "supergroup"}:
        return
    settings = await get_settings(message.chat.id)
    if settings["delete_service_messages"]:
        try:
            await message.delete()
        except Exception:
            pass


async def send_unsafe_file_to_secret_group(message: types.Message, reason: str, filename: str):
    private_log_chat_id = await get_private_log_chat_id()
    if not private_log_chat_id:
        return

    caption = (
        "🦠 <b>Zararli fayl ushlandi</b>\n\n"
        f"👥 Guruh: <b>{escape(message.chat.title or str(message.chat.id))}</b>\n"
        f"🆔 Guruh ID: <code>{message.chat.id}</code>\n"
        f"👤 Yuborgan: <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.full_name)}</a>\n"
        f"🆔 User ID: <code>{message.from_user.id}</code>\n"
        f"📄 Fayl: <code>{escape(filename)}</code>\n"
        f"⚠️ Sabab: <b>{escape(reason)}</b>"
    )

    try:
        # file_id orqali yuborish tez ishlaydi, lekin tarmoq timeout bo‘lsa ham asosiy guruhdagi fayl o‘chirilgan bo‘ladi.
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


@router.message(F.content_type == "document")
async def remove_unsafe_files(message: types.Message):
    if message.chat.type not in {"group", "supergroup"} or not message.from_user or not message.document:
        return

    await add_or_update_user(message.from_user)

    # Faqat superadmin va whitelist o'tib ketsin. Oddiy guruh adminlari ham zararli fayl tashlasa bloklanadi.
    if is_super_admin(message.from_user.id):
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

    # Avval guruhdan o'chiramiz. Maxfiy guruhga yuborishda timeout bo'lsa ham zararli fayl guruhda qolmaydi.
    deleted = False
    try:
        await message.delete()
        deleted = True
    except Exception as exc:
        logger.exception("Zararli faylni guruhdan o‘chirishda xato: %s", exc)

    await send_unsafe_file_to_secret_group(message, reason, filename)

    await add_security_log(message.chat.id, message.from_user.id, "Fayl o‘chirildi" if deleted else "Faylni o‘chirishda xato", reason, filename)
    warn_count = await add_warning(message.chat.id, message.from_user.id)

    text = (
        f"🦠 <a href='tg://user?id={message.from_user.id}'>{escape(message.from_user.full_name)}</a>, "
        f"faylingiz xavfsizlik sababli o‘chirildi.\n"
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
