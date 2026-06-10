from .common import *

router = Router()

REF_ADD_RIGHTS = "delete_messages+restrict_members+invite_users+pin_messages"


def referral_group_url(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?startgroup={code}&admin={REF_ADD_RIGHTS}"


def referral_channel_url(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?startchannel={code}&admin={REF_ADD_RIGHTS}"


def referral_private_url(bot_username: str, code: str) -> str:
    return f"https://t.me/{bot_username}?start={code}"


async def refresh_referral_statuses(bot, link_id: int | None = None):
    """Referral statistikasi ochilganda botning admin/member holatini Telegramdan yangilaydi."""
    seen: set[int] = set()
    if link_id is not None:
        link_ids = [link_id]
    else:
        link_ids = [row[0] for row in await get_referral_stats()]

    for lid in link_ids:
        for row in await get_referral_chats(lid):
            chat_id = row[0]
            if chat_id in seen:
                continue
            seen.add(chat_id)
            await refresh_one_chat_status(bot, chat_id)

async def referral_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    perms = await get_admin_effective_permissions(user_id) if not is_super_admin(user_id) else set(PANEL_PERMISSIONS)
    rows = []
    if can_create(perms, "referrals"):
        rows.append([InlineKeyboardButton(text="➕ Yangi giper ssilka", callback_data="ref:create")])
    if can_read(perms, "referrals"):
        rows.append([InlineKeyboardButton(text="📊 Ssilka statistikasi", callback_data="ref:list")])
        # rows.append([InlineKeyboardButton(text="🧩 Biriktirilmagan guruhlar", callback_data="ref:unlinked:0")])
    rows.append([InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "ref:menu")
async def referral_menu(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "referrals"):
        return

    await state.clear()
    await call.message.edit_text(
        "🔗 <b>Giper ssilkalar</b>\n\n"
        "Bu yerda botni guruhlarga qo‘shish uchun cheksiz havola yaratish va har bir havola statistikalarini ko‘rish mumkin.",
        reply_markup=await referral_menu_kb(call.from_user.id)
    )
    await call.answer()


@router.callback_query(F.data == "ref:create")
async def referral_create_start(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "referrals.create"):
        return
    await state.set_state(ReferralStates.enter_name)
    await call.message.edit_text("Yangi ssilka nomini yuboring. Masalan: <b>Instagram reklama</b>", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(ReferralStates.enter_name)
async def referral_create_finish(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "referrals.create"):
        return

    name = (message.text or "").strip()[:100] or "Nomsiz havola"
    code = "ref_" + secrets.token_urlsafe(6).replace("-", "_")
    await create_referral_link(name, code, message.from_user.id)

    bot_username = (await message.bot.me()).username
    public_url = referral_private_url(bot_username, code)

    await message.answer(
        "✅ <b>Yangi giper ssilka yaratildi</b>\n\n"
        f"🏷 Nomi: <b>{escape(name)}</b>\n\n"
        f"🔗 <b>Tarqatiladigan giper ssilka:</b>\n<code>{escape(public_url)}</code>\n\n"
        "Shu bitta ssilkani istalgan foydalanuvchiga yuboring. Ular ham shu ssilkani boshqalarga ulashishi mumkin. "
        "Kim shu ssilkani bosib private chatga kirsa, bot ref kodni eslab qoladi va guruh/kanalga qo‘shish tugmalarini beradi. "
        "Keyin o‘sha foydalanuvchi botni o‘z guruhiga admin qilib qo‘shsa, guruh aynan shu ssilka statistikasi ichida ko‘rinadi.\n\n"
        "⚠️ Muhim: Telegram direct <code>startgroup</code> linkidan my_chat_member eventida ref kodni doim qaytarmaydi. "
        "Shuning uchun tarqatiladigan asosiy ssilka private <code>?start=ref_...</code> ko‘rinishida bo‘ladi; guruhga qo‘shish tugmasi bot ichida chiqadi.",
        reply_markup=await referral_menu_kb(message.from_user.id)
    )
    await state.clear()


@router.callback_query(F.data.startswith("ref:list"))
async def referral_list(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.read"):
        return

    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    await refresh_referral_statuses(call.bot)
    rows = await get_referral_stats()
    total = len(rows)
    if not rows:
        await call.message.edit_text("🔗 Hozircha ssilka yaratilmagan.", reply_markup=await referral_menu_kb(call.from_user.id))
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
        public_url = referral_private_url(bot_username, code)
        text += (
            f"{number}. 🔹 <b>{escape(name)}</b>\n"
            f"🛡 Bot admin bo‘lgan guruh/kanallar: <b>{admin_count}</b>\n"
            f"🔗 Giper ssilka: <code>{escape(public_url)}</code>\n\n"
        )
        kb_rows.append([InlineKeyboardButton(
            text=f"📄 {number}. {name[:30]} ({admin_count})",
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
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("ref:detail:"))
async def referral_detail(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.read"):
        return

    parts = call.data.split(":")
    link_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    back_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0

    await refresh_referral_statuses(call.bot, link_id)
    stats_rows = await get_referral_stats()
    current_link = next((row for row in stats_rows if row[0] == link_id), None)
    all_chats = await get_referral_chats(link_id)
    chats = [row for row in all_chats if row[3] == 1]
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
            f"Bot admin bo‘lganlari: <b>{admin_count}</b>\n\n"
        )
    else:
        text = "📄 <b>Ssilka orqali qo‘shilgan guruhlar</b>\n\n"

    if not chats:
        text += "Bu ssilka orqali bot admin qilingan guruh/kanal topilmadi."
    else:
        for number, row in enumerate(page_chats, start=start + 1):
            chat_id, title, chat_type, is_admin, bot_status, added_at, added_by = row
            status = render_bot_status(is_admin, bot_status)
            added_by_text = f" | Kim qo‘shgan: <code>{added_by}</code>" if added_by else ""
            text += (
                f"{number}. <b>{escape(title or str(chat_id))}</b>\n"
                f"   ID: <code>{chat_id}</code> | {status}\n"
                f"   Qo‘shilgan: <code>{escape(str(added_at))}</code>{added_by_text}\n\n"
            )

    kb_rows = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ref:detail:{link_id}:{page - 1}:{back_page}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"ref:detail:{link_id}:{page + 1}:{back_page}"))
    if nav:
        kb_rows.append(nav)

    action_row = []
    if await has_panel_access(call.from_user.id, "referrals.update"):
        action_row.append(InlineKeyboardButton(text="✏️ Nomini tahrirlash", callback_data=f"ref:edit:{link_id}:{back_page}"))
    if await has_panel_access(call.from_user.id, "referrals.delete"):
        action_row.append(InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"ref:delask:{link_id}:{back_page}"))
    if action_row:
        kb_rows.append(action_row)

    kb_rows.append([
        InlineKeyboardButton(text="📄 TXT yuklab olish", callback_data=f"ref:export:txt:{link_id}:{back_page}"),
        InlineKeyboardButton(text="📕 PDF yuklab olish", callback_data=f"ref:export:pdf:{link_id}:{back_page}"),
    ])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Statistikaga qaytish", callback_data=f"ref:list:{back_page}")])
    kb_rows.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("ref:export:"))
async def referral_export_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.read"):
        return

    parts = call.data.split(":")
    export_type = parts[2]
    link_id = int(parts[3])
    back_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0

    await refresh_referral_statuses(call.bot, link_id)
    link = await get_referral_link_by_id(link_id)
    if not link:
        await call.answer("❌ Ssilka topilmadi.", show_alert=True)
        return

    _, link_name, code, _, _ = link
    bot_username = (await call.bot.me()).username
    public_url = referral_private_url(bot_username, code)
    chats = [row for row in await get_referral_chats(link_id) if row[3] == 1]

    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(link_name or link_id)).strip("_")[:40] or str(link_id)
    if export_type == "txt":
        file_path = export_referral_chats_to_txt(link_name, public_url, chats, filename=f"referral_{link_id}_{safe_name}.txt")
        caption = "✅ TXT tayyor."
    elif export_type == "pdf":
        file_path = export_referral_chats_to_pdf(link_name, public_url, chats, filename=f"referral_{link_id}_{safe_name}.pdf")
        caption = "✅ PDF tayyor."
    else:
        await call.answer("❌ Noto‘g‘ri export turi.", show_alert=True)
        return

    await call.message.answer_document(types.FSInputFile(file_path), caption=caption)
    await call.answer("✅ Fayl yuborildi")


@router.callback_query(F.data.startswith("ref:edit:"))
async def referral_edit_start(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "referrals.update"):
        return

    parts = call.data.split(":")
    link_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    link = await get_referral_link_by_id(link_id)
    if not link:
        await call.answer("❌ Ssilka topilmadi.", show_alert=True)
        return

    await state.update_data(ref_edit_link_id=link_id, ref_edit_back_page=back_page)
    await state.set_state(ReferralStates.edit_name)
    await call.message.edit_text(
        f"✏️ Hozirgi nomi: <b>{escape(link[1])}</b>\n\nYangi nomni yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data=f"ref:detail:{link_id}:0:{back_page}")]
        ])
    )
    await call.answer()


@router.message(ReferralStates.edit_name)
async def referral_edit_finish(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "referrals.update"):
        return

    data = await state.get_data()
    link_id = int(data.get("ref_edit_link_id", 0))
    back_page = int(data.get("ref_edit_back_page", 0))
    name = (message.text or "").strip()[:100] or "Nomsiz havola"
    ok = await update_referral_link_name(link_id, name)
    await state.clear()
    await message.answer(
        "✅ Giper ssilka nomi yangilandi." if ok else "❌ Ssilka topilmadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Ssilkani ochish", callback_data=f"ref:detail:{link_id}:0:{back_page}")],
            [InlineKeyboardButton(text="📊 Statistikaga qaytish", callback_data=f"ref:list:{back_page}")],
        ])
    )


@router.callback_query(F.data.startswith("ref:delask:"))
async def referral_delete_ask(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.delete"):
        return

    parts = call.data.split(":")
    link_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    link = await get_referral_link_by_id(link_id)
    if not link:
        await call.answer("❌ Ssilka topilmadi.", show_alert=True)
        return

    await call.message.edit_text(
        f"🗑 <b>{escape(link[1])}</b> ssilkasini o‘chirasizmi?\n\n"
        "Bu faqat ssilka va unga bog‘langan statistikani o‘chiradi. Guruhlar bazadan o‘chmaydi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Ha, o‘chirish", callback_data=f"ref:del:{link_id}:{back_page}")],
            [InlineKeyboardButton(text="⬅️ Yo‘q", callback_data=f"ref:detail:{link_id}:0:{back_page}")],
        ])
    )
    await call.answer()


@router.callback_query(F.data.startswith("ref:del:"))
async def referral_delete_finish(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.delete"):
        return

    parts = call.data.split(":")
    link_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    ok = await delete_referral_link(link_id)
    await call.answer("✅ O‘chirildi." if ok else "❌ Ssilka topilmadi.", show_alert=True)
    await call.message.edit_text(
        "✅ Giper ssilka o‘chirildi." if ok else "❌ Ssilka topilmadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistikaga qaytish", callback_data=f"ref:list:{back_page}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ref:menu")],
        ])
    )


@router.callback_query(F.data.startswith("ref:unlinked:"))
async def referral_unlinked_chats(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.read"):
        return

    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    chats = await get_chats_without_referral()
    total = len(chats)

    if not chats:
        await call.message.edit_text(
            "✅ Hamma saqlangan guruh/kanallar referral ssilkaga biriktirilgan.",
            reply_markup=await referral_menu_kb(call.from_user.id)
        )
        return await call.answer()

    max_page = max((total - 1) // REF_GROUPS_PER_PAGE, 0)
    page = max(0, min(page, max_page))
    start = page * REF_GROUPS_PER_PAGE
    end = start + REF_GROUPS_PER_PAGE

    text = (
        "🧩 <b>Ssilkaga biriktirilmagan guruh/kanallar</b>\n"
        f"Sahifa: <b>{page + 1}/{max_page + 1}</b> | Jami: <b>{total}</b>\n\n"
        "Maxfiy guruhlarda Telegram ba’zan startgroup payloadni yubormaydi. "
        "Shunda guruh bazaga tushadi, lekin qaysi ssilka orqali kelgani bilinmaydi. Quyidan qo‘lda biriktiring.\n\n"
    )
    kb_rows = []
    for number, row in enumerate(chats[start:end], start=start + 1):
        chat_id, title, chat_type, invite_link, is_admin, bot_status = row
        text += f"{number}. <b>{escape(title or str(chat_id))}</b> — {render_bot_status(is_admin, bot_status)}\n"
        kb_rows.append([InlineKeyboardButton(
            text=f"🔗 {number}. {(title or str(chat_id))[:30]}",
            callback_data=f"ref:pickchat:{chat_id}:{page}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ref:unlinked:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"ref:unlinked:{page + 1}"))
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="ref:menu")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("ref:pickchat:"))
async def referral_pick_chat(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.update"):
        return

    parts = call.data.split(":")
    chat_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    links = await get_referral_stats()

    if not links:
        await call.message.edit_text("🔗 Avval giper ssilka yarating.", reply_markup=await referral_menu_kb(call.from_user.id))
        return await call.answer()

    rows = []
    for link_id, name, code, groups_count, admin_count, created_at in links[:40]:
        rows.append([InlineKeyboardButton(
            text=f"{name[:35]} ({groups_count})",
            callback_data=f"ref:assign:{link_id}:{chat_id}:{back_page}"
        )])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"ref:unlinked:{back_page}")])

    await call.message.edit_text(
        "Qaysi giper ssilkaga biriktirasiz?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await call.answer()


@router.callback_query(F.data.startswith("ref:assign:"))
async def referral_assign_chat(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "referrals.update"):
        return

    parts = call.data.split(":")
    link_id = int(parts[2])
    chat_id = int(parts[3])
    back_page = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
    ok = await assign_chat_to_referral(link_id, chat_id)
    await call.answer("✅ Biriktirildi." if ok else "❌ Biriktirib bo‘lmadi.", show_alert=True)
    await call.message.edit_text(
        "✅ Guruh/kanal ssilkaga biriktirildi." if ok else "❌ Guruh yoki ssilka topilmadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Biriktirilmaganlarga qaytish", callback_data=f"ref:unlinked:{back_page}")],
            [InlineKeyboardButton(text="📊 Ssilka statistikasi", callback_data="ref:list")],
        ])
    )


@router.callback_query(F.data == "help_info")
async def show_help(call: types.CallbackQuery):
    await call.message.edit_text(
        "📖 <b>Qo‘llanma</b>\n\n"
        "1️⃣ Botni guruhingizga qo‘shing.\n"
        "2️⃣ Botni administrator qiling va xabarlarni o‘chirish hamda foydalanuvchilarni cheklash huquqlarini bering.\n"
        "3️⃣ Boshqaruv paneli orqali taqiqlangan so‘zlar, bloklanadigan fayl turlari va qoidabuzarlarga qo‘llaniladigan choralarni sozlang.\n"
        "4️⃣ Ishonchli foydalanuvchilarni istisno ro‘yxatiga qo‘shishingiz mumkin.\n\n"
        "✅ Shundan so‘ng bot guruhingizni avtomatik nazorat qiladi va qoidabuzarlarga qarshi choralar ko‘radi.",
        reply_markup=back_to_main_kb()
    )
    await call.answer()


@router.callback_query(F.data == "menu:main")
async def go_main_menu(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call):
        return
    await state.clear()
    await call.message.edit_text("🏠 <b>Asosiy menyu</b>", reply_markup=await panel_menu_kb(call.from_user.id))
    await call.answer()

@router.callback_query(F.data == "stats")
async def statistics_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "stats.read"):
        return

    await call.answer("⏳ Statistika yuklanmoqda...")

    stats = await get_stats_summary()

    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Guruh/kanallar: <b>{stats['chats_count']}</b>\n"
        f"🛡 Bot admin bo‘lgan guruh/kanallar: <b>{stats['bot_admin_chats']}</b>\n"
        f"🚪 Bot a’zo bo‘lmagan guruh/kanallar: <b>{stats['not_member_chats']}</b>\n"
        f"👤 Saqlangan foydalanuvchilar: <b>{stats['users_count']}</b>\n"
        f"🦠 Global xavfli kengaytmalar: <b>{stats['unsafe_ext_count']}</b>\n"
        f"🚫 Global yomon so‘zlar: <b>{stats['bad_words_count']}</b>\n\n"
        "ℹ️ Bu tezkor statistika bazadan olinadi.\n"
        "🔄 Guruh statuslarini alohida yangilash tavsiya qilinadi."
    )

    await safe_edit_text(call.message, text, reply_markup=stats_kb())


@router.callback_query(F.data.startswith("chats:page:"))
async def chats_page_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "chats.read"):
        return

    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    chats = await refresh_all_chat_statuses(call.bot)
    total = len(chats)

    if not chats:
        await call.message.edit_text("📋 Hozircha guruh yoki kanal yo‘q.", reply_markup=stats_kb())
        return await call.answer()

    max_page = max((total - 1) // CHATS_PER_PAGE, 0)
    page = max(0, min(page, max_page))
    start = page * CHATS_PER_PAGE
    end = start + CHATS_PER_PAGE

    text = f"📋 <b>Guruh/kanallar ro‘yxati</b>\nSahifa: <b>{page + 1}/{max_page + 1}</b> | Jami: <b>{total}</b>\n\n"
    kb_rows = []

    for number, row in enumerate(chats[start:end], start=start + 1):
        chat_id, title, chat_type, invite_link, is_admin, bot_status = row
        text += (
            f"{number}. <b>{escape(title or str(chat_id))}</b>\n"
            f"   Turi: <code>{escape(str(chat_type))}</code> | {render_bot_status(is_admin, bot_status)}\n"
            f"   ID: <code>{chat_id}</code>\n\n"
        )
        kb_rows.append([InlineKeyboardButton(
            text=f"{number}. {(title or str(chat_id))[:32]}",
            callback_data=f"chats:detail:{chat_id}:{page}"
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"chats:page:{page - 1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"chats:page:{page + 1}"))
    if nav:
        kb_rows.append(nav)

    kb_rows.append([InlineKeyboardButton(text="⬅️ Statistikaga qaytish", callback_data="stats")])
    kb_rows.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data.startswith("chats:detail:"))
async def chat_detail_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "chats.read"):
        return

    parts = call.data.split(":")
    chat_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

    await refresh_one_chat_status(call.bot, chat_id)
    chats = await get_all_chats()
    row = next((c for c in chats if c[0] == chat_id), None)
    if not row:
        await call.message.edit_text("❌ Bu chat bazadan topilmadi.", reply_markup=stats_kb())
        return await call.answer()

    chat_id, title, chat_type, invite_link, is_admin, bot_status = row
    text = (
        f"📌 <b>{escape(title or str(chat_id))}</b>\n\n"
        f"ID: <code>{chat_id}</code>\n"
        f"Turi: <code>{escape(str(chat_type))}</code>\n"
        f"Status: {render_bot_status(is_admin, bot_status)}\n"
        f"Link: {escape(invite_link or 'yo‘q')}\n\n"
    )

    if bot_status in {"not_member", "left", "kicked"}:
        text += "⚠️ Bot bu guruh/kanalda a’zo emas. Kerak bo‘lsa bazadan o‘chirishingiz mumkin."
    elif not is_admin:
        text += "⚠️ Bot a’zo, lekin admin emas. Telegramda botga admin huquqlarini bering."
    else:
        text += "✅ Bot admin."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Statusni tekshirish", callback_data=f"chats:detail:{chat_id}:{back_page}")],
        [InlineKeyboardButton(text="🗑 Bazadan o‘chirish", callback_data=f"chats:delete:{chat_id}:{back_page}")],
        [InlineKeyboardButton(text="⬅️ Ro‘yxatga qaytish", callback_data=f"chats:page:{back_page}")],
        [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")],
    ])
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("chats:delete:"))
async def chat_delete_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "chats.delete"):
        return

    parts = call.data.split(":")
    chat_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    deleted = await delete_chat(chat_id)
    await call.answer("✅ Bazadan o‘chirildi." if deleted else "❌ Bazada topilmadi.", show_alert=True)
    await call.message.edit_text(
        "✅ Chat bazadan o‘chirildi." if deleted else "❌ Chat bazada topilmadi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Ro‘yxatga qaytish", callback_data=f"chats:page:{back_page}")],
            [InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")],
        ])
    )


@router.callback_query(F.data == "logs")
async def logs_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "logs.read"):
        return
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
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()



@router.callback_query(F.data == "export:txt")
async def export_txt_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "exports.action"):
        return
    chats = await get_all_chats()
    print(chats)
    file_path = export_chats_to_txt(chats)
    await call.message.answer_document(types.FSInputFile(file_path))
    await call.answer("✅ TXT tayyor")


@router.callback_query(F.data == "export:pdf")
async def export_pdf_handler(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "exports.action"):
        return
    chats = await get_all_chats()
    print(chats)
    file_path = export_chats_to_pdf(chats)
    await call.message.answer_document(types.FSInputFile(file_path))
    await call.answer("✅ PDF tayyor")


@router.callback_query(F.data == "bw:menu")
async def bad_words_menu(call: types.CallbackQuery):
    if call.message.chat.type == "private":
        if await deny_if_no_permission(call, "bad_words"):
            return
        perms = await get_admin_effective_permissions(call.from_user.id) if not is_super_admin(call.from_user.id) else set(PANEL_PERMISSIONS)
    elif not await is_group_admin(call):
        return await call.answer("⛔ Siz admin emassiz.", show_alert=True)
    else:
        perms = set(PANEL_PERMISSIONS)
    rows = []
    if can_create(perms, "bad_words"):
        rows.append([InlineKeyboardButton(text="➕ So‘z qo‘shish", callback_data="bw:add")])
    if can_delete(perms, "bad_words"):
        rows.append([InlineKeyboardButton(text="➖ So‘z o‘chirish", callback_data="bw:remove")])
    if can_read(perms, "bad_words"):
        rows.append([
            InlineKeyboardButton(text="📃 Global ro‘yxat", callback_data="bw:list:g"),
            InlineKeyboardButton(text="📃 Chat ro‘yxati", callback_data="bw:list:c"),
        ])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await call.message.edit_text("🛡 <b>Yomon so‘zlar boshqaruvi</b>", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "bw:add")
async def bw_add_prompt(call: types.CallbackQuery, state: FSMContext):
    if call.message.chat.type == "private":
        if await deny_if_no_permission(call, "bad_words.create"):
            return
    elif not await is_group_admin(call):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    await state.set_state(BadWordStates.add_words)
    await call.message.edit_text("Qo‘shiladigan so‘zlarni vergul yoki yangi qatorda yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(BadWordStates.add_words, F.text)
async def bw_add_take(message: types.Message, state: FSMContext):
    if message.chat.type == "private":
        if not await has_panel_access(message.from_user.id, "bad_words.create"):
            return
        target_chat = None
    else:
        if not await is_group_admin(message):
            return
        target_chat = message.chat.id
    items = normalize_items(message.text)
    added = 0
    for word in items:
        if await add_bad_word(word, target_chat):
            added += 1
    await message.answer(f"✅ {added} ta so‘z qo‘shildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "bw:remove")
async def bw_remove_prompt(call: types.CallbackQuery, state: FSMContext):
    if call.message.chat.type == "private":
        if await deny_if_no_permission(call, "bad_words.delete"):
            return
    elif not await is_group_admin(call):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    await state.set_state(BadWordStates.remove_words)
    await call.message.edit_text("O‘chiriladigan so‘zlarni vergul yoki yangi qatorda yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(BadWordStates.remove_words, F.text)
async def bw_remove_take(message: types.Message, state: FSMContext):
    if message.chat.type == "private":
        if not await has_panel_access(message.from_user.id, "bad_words.delete"):
            return
        target_chat = None
    else:
        if not await is_group_admin(message):
            return
        target_chat = message.chat.id
    removed = 0
    for word in normalize_items(message.text):
        if await remove_bad_word(word, target_chat):
            removed += 1
    await message.answer(f"🗑 {removed} ta so‘z o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data.in_({"bw:list:g", "bw:list:c"}))
async def list_words(call: types.CallbackQuery):
    if call.message.chat.type == "private":
        if await deny_if_no_permission(call, "bad_words.read"):
            return
        chat_id = None
    else:
        if not await is_group_admin(call):
            return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
        chat_id = None if call.data == "bw:list:g" else call.message.chat.id
    words = await list_bad_words(chat_id)
    title = "Global yomon so‘zlar" if chat_id is None else "Ushbu chatdagi yomon so‘zlar"
    text = f"📃 <b>{title}</b>\n\n" + ("\n".join(f"• {escape(w)}" for w in words) if words else "Ro‘yxat bo‘sh.")
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "ext:menu")
async def ext_menu(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "extensions"):
        return
    perms = await get_admin_effective_permissions(call.from_user.id) if not is_super_admin(call.from_user.id) else set(PANEL_PERMISSIONS)
    rows = []
    if can_create(perms, "extensions"):
        rows.append([InlineKeyboardButton(text="➕ Kengaytma qo‘shish", callback_data="ext:add")])
    if can_delete(perms, "extensions"):
        rows.append([InlineKeyboardButton(text="➖ Kengaytma o‘chirish", callback_data="ext:remove")])
        rows.append([InlineKeyboardButton(text="🗑 Barchasini o‘chirish", callback_data="ext:remove_all")])
    if can_read(perms, "extensions"):
        rows.append([InlineKeyboardButton(text="📃 Ro‘yxat", callback_data="ext:list")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await call.message.edit_text("🦠 <b>Xavfli fayl kengaytmalari</b>", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "ext:add")
async def ext_add_prompt(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "extensions.create"):
        return
    await state.set_state(ExtStates.add_ext)
    await call.message.edit_text("Qo‘shiladigan kengaytmalarni yuboring. Masalan: <code>.exe, .apk, .js</code>", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(ExtStates.add_ext, F.text)
async def ext_add_take(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "extensions.create"):
        return
    for ext in normalize_items(message.text):
        await add_unsafe_extension(ext, None)
    await message.answer("✅ Kengaytmalar qo‘shildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "ext:remove")
async def ext_remove_prompt(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "extensions.delete"):
        return
    await state.set_state(ExtStates.remove_ext)
    await call.message.edit_text("O‘chiriladigan kengaytmalarni yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(ExtStates.remove_ext, F.text)
async def ext_remove_take(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "extensions.delete"):
        return
    for ext in normalize_items(message.text):
        await remove_unsafe_extension(ext, None)
    await message.answer("🗑 Kengaytmalar o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "ext:remove_all")
async def ext_remove_all(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "extensions.delete"):
        return
    await remove_unsafe_all_extensions(None)
    await call.message.answer("🗑 Barcha xavfli kengaytmalar o‘chirildi.", reply_markup=back_to_main_kb())
    await call.answer()

@router.callback_query(ExtStates.remove_all, F.data == "ext:remove_all")
async def ext_remove_all_confirm(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "extensions.delete"):
        return
    await remove_unsafe_all_extensions(None)
    await call.message.answer("🗑 Barcha xavfli kengaytmalar o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()
    await call.answer()


@router.callback_query(F.data == "ext:list")
async def ext_list(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "extensions.read"):
        return
    exts = await list_unsafe_extensions(None)
    text = "🦠 <b>Xavfli kengaytmalar</b>\n\n" + ("\n".join(f"• <code>{escape(e)}</code>" for e in exts) if exts else "Ro‘yxat bo‘sh.")
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


@router.callback_query(F.data == "settings:menu")
async def settings_menu(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "settings"):
        return
    perms = await get_admin_effective_permissions(call.from_user.id) if not is_super_admin(call.from_user.id) else set(PANEL_PERMISSIONS)
    rows = []
    if can_update(perms, "settings"):
        rows.extend([
            [InlineKeyboardButton(text="⏱ Mute vaqti", callback_data="set:mute_minutes")],
            [InlineKeyboardButton(text="⚠️ Ogohlantirish limiti", callback_data="set:max_warnings")],
            [InlineKeyboardButton(text="📦 Maksimal fayl MB", callback_data="set:max_file_mb")],
            [InlineKeyboardButton(text="📁 Arxivlarni bloklash", callback_data="set:block_archives")],
        ])
    if not rows:
        rows.append([InlineKeyboardButton(text="⛔ Faqat ko‘rish huquqida sozlama o‘zgartirib bo‘lmaydi", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await call.message.edit_text("⚙️ <b>Guruh sozlamalari</b>\nAvval sozlama turini tanlang.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("set:"))
async def setting_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "settings.update"):
        return
    key = call.data.split(":", 1)[1]
    await state.update_data(setting_key=key)
    await state.set_state(SettingStates.choose_chat)
    await call.message.edit_text("Qaysi guruh uchun sozlama o‘zgartiriladi?", reply_markup=await choose_chat_keyboard("setting", 0))
    await call.answer()


@router.callback_query(F.data.startswith("setting:page:"), SettingStates.choose_chat)
async def setting_page(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "settings.update"):
        return
    page = int(call.data.split(":")[2])
    await call.message.edit_reply_markup(reply_markup=await choose_chat_keyboard("setting", page))
    await call.answer()


@router.callback_query(F.data == "setting:all", SettingStates.choose_chat)
async def setting_all_selected(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "settings.update"):
        return
    data = await state.get_data()
    key = data["setting_key"]
    await state.update_data(chat_id="all")
    settings = await get_global_settings()
    labels = {
        "mute_minutes": "Mute vaqti daqiqada",
        "max_warnings": "Ogohlantirish limiti",
        "max_file_mb": "Maksimal fayl hajmi MB",
        "block_archives": "Arxivlarni bloklash: 1 = ha, 0 = yo‘q",
    }
    await state.set_state(SettingStates.enter_value)
    await call.message.edit_text(
        f"🌐 <b>Barcha guruh/kanallar uchun</b>\n"
        f"Joriy umumiy qiymat: <code>{settings[key]}</code>\n\n"
        f"{labels[key]} uchun yangi qiymat yuboring. Bu qiymat bazadagi barcha guruhlarga va keyin qo‘shiladigan yangi guruhlarga ham qo‘llanadi.",
        reply_markup=back_to_settings_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("setting:chat:"), SettingStates.choose_chat)
async def setting_chat_selected(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "settings.update"):
        return
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
    if not await has_panel_access(message.from_user.id, "settings.update"):
        return
    data = await state.get_data()
    key = data.get("setting_key")
    chat_target = data.get("chat_id")
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
    if chat_target == "all":
        changed_count = await update_setting_for_all_chats(key, value)
        await message.answer(
            f"✅ Umumiy sozlama saqlandi.\n"
            f"🌐 Bazadagi <b>{changed_count}</b> ta guruh/kanalga qo‘llandi.\n"
            "Keyin qo‘shiladigan guruh/kanallar ham shu qiymatni oladi.",
            reply_markup=back_to_main_kb()
        )
    else:
        chat_id = int(chat_target)
        await update_setting(chat_id, key, value)
        await message.answer("✅ Sozlama saqlandi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:menu")
async def whitelist_menu(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "whitelist"):
        return
    perms = await get_admin_effective_permissions(call.from_user.id) if not is_super_admin(call.from_user.id) else set(PANEL_PERMISSIONS)
    rows = []
    if can_create(perms, "whitelist"):
        rows.append([InlineKeyboardButton(text="➕ Foydalanuvchi qo‘shish", callback_data="wh:add:choose_chat")])
    if can_delete(perms, "whitelist"):
        rows.append([InlineKeyboardButton(text="➖ Foydalanuvchini o‘chirish", callback_data="wh:rem:choose_chat")])
    if can_read(perms, "whitelist"):
        rows.append([InlineKeyboardButton(text="📃 Oq ro‘yxat", callback_data="wh:list")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await call.message.edit_text("✅ <b>Oq ro‘yxat</b>\nBu ro‘yxatdagi foydalanuvchilarning fayllari bloklanmaydi.", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "wh:add:choose_chat")
async def wh_add_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "whitelist.create"):
        return
    await state.set_state(WhitelistStates.add_choose_chat)
    await call.message.edit_text("Qaysi guruhga foydalanuvchi qo‘shiladi?", reply_markup=await choose_chat_keyboard("whadd", 0))
    await call.answer()


@router.callback_query(F.data.startswith("whadd:chat:"), WhitelistStates.add_choose_chat)
async def wh_add_got_chat(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "whitelist.create"):
        return
    await state.update_data(chat_id=int(call.data.split(":")[2]))
    await state.set_state(WhitelistStates.add_enter_user)
    await call.message.edit_text("Foydalanuvchi ID raqamini yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(WhitelistStates.add_enter_user, F.text.regexp(r"^\d+$"))
async def wh_add_user(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "whitelist.create"):
        return
    data = await state.get_data()
    user_id = int(message.text)
    await add_whitelist_user(int(data["chat_id"]), user_id)
    await message.answer(f"✅ <code>{user_id}</code> oq ro‘yxatga qo‘shildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:rem:choose_chat")
async def wh_rem_choose_chat(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "whitelist.delete"):
        return
    await state.set_state(WhitelistStates.rem_choose_chat)
    await call.message.edit_text("Qaysi guruhdan foydalanuvchi o‘chiriladi?", reply_markup=await choose_chat_keyboard("whrem", 0))
    await call.answer()


@router.callback_query(F.data.startswith("whrem:chat:"), WhitelistStates.rem_choose_chat)
async def wh_rem_got_chat(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "whitelist.delete"):
        return
    await state.update_data(chat_id=int(call.data.split(":")[2]))
    await state.set_state(WhitelistStates.rem_enter_user)
    await call.message.edit_text("O‘chiriladigan foydalanuvchi ID raqamini yuboring.", reply_markup=back_to_main_kb())
    await call.answer()


@router.message(WhitelistStates.rem_enter_user, F.text.regexp(r"^\d+$"))
async def wh_remove_user(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "whitelist.delete"):
        return
    data = await state.get_data()
    user_id = int(message.text)
    await remove_whitelist_user(int(data["chat_id"]), user_id)
    await message.answer(f"🗑 <code>{user_id}</code> oq ro‘yxatdan o‘chirildi.", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data == "wh:list")
async def wh_list_all(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "whitelist.read"):
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
    await call.message.edit_text(text, reply_markup=back_to_main_kb())
    await call.answer()


def broadcast_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Faqat foydalanuvchilarga", callback_data="media:target:users")],
        [InlineKeyboardButton(text="👥 Faqat guruhlarga", callback_data="media:target:chats")],
        [InlineKeyboardButton(text="🌐 Hammaga", callback_data="media:target:all")],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:main")],
    ])


@router.callback_query(F.data == "media:start")
async def ask_media_target(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "broadcast.action"):
        return
    await state.set_state(MediaState.choose_target)
    await safe_edit_text(
        call.message,
        "🖼 <b>Ommaviy xabar</b>\n\n"
        "Xabar qayerga yuborilsin?\n\n"
        "• <b>Foydalanuvchilar</b> — botga /start bosgan shaxsiy userlar.\n"
        "• <b>Guruhlar</b> — bot qo‘shilgan guruh/kanallar.\n"
        "• <b>Hammaga</b> — ikkalasiga ham.\n\n"
        "Keyingi qadamda yubormoqchi bo‘lgan xabaringizni tashlaysiz. Rasm, video, fayl va formatlangan matn copy holatida saqlanadi.",
        reply_markup=broadcast_target_kb(),
    )
    await call.answer()


@router.callback_query(F.data.startswith("media:target:"), MediaState.choose_target)
async def ask_media_post(call: types.CallbackQuery, state: FSMContext):
    if await deny_if_no_permission(call, "broadcast.action"):
        return
    target = call.data.split(":", 2)[2]
    if target not in {"users", "chats", "all"}:
        return await call.answer("Noto‘g‘ri yo‘nalish.", show_alert=True)
    await state.update_data(broadcast_target=target)
    await state.set_state(MediaState.waiting_media)
    target_label = {"users": "foydalanuvchilarga", "chats": "guruhlarga", "all": "hammaga"}[target]
    await safe_edit_text(
        call.message,
        f"✅ Yo‘nalish tanlandi: <b>{target_label}</b>.\n\n"
        "Endi yuboriladigan xabarni tashlang.\n\n"
        "Maslahat: Telegramda linklar chiroyli chiqishi uchun xabarni o‘zingiz formatlab yuboring. Men uni <b>copy_to</b> orqali aynan shu ko‘rinishda tarqataman.",
        reply_markup=back_to_main_kb(),
    )
    await call.answer()


@router.message(MediaState.waiting_media)
async def broadcast_media_post(message: types.Message, state: FSMContext):
    if not await has_panel_access(message.from_user.id, "broadcast.action"):
        return

    data = await state.get_data()
    target = data.get("broadcast_target", "chats")
    recipients: list[int] = []

    if target in {"users", "all"}:
        users = await get_all_users()
        recipients.extend(int(user_id) for user_id, *_ in users if int(user_id) != message.from_user.id)

    if target in {"chats", "all"}:
        chats = await get_all_chats()
        recipients.extend(int(chat_id) for chat_id, *_ in chats)

    recipients = list(dict.fromkeys(recipients))
    sent = 0
    failed = 0

    progress = await message.answer(f"⏳ Ommaviy yuborish boshlandi. Jami: <b>{len(recipients)}</b>")

    for index, chat_id in enumerate(recipients, start=1):
        try:
            await message.copy_to(chat_id)
            sent += 1
        except Exception as exc:
            logger.warning("Broadcast yuborilmadi. chat_id=%s error=%s", chat_id, exc)
            failed += 1
        await asyncio.sleep(0.07)

        if index % 25 == 0:
            await safe_edit_text(progress, f"⏳ Yuborilmoqda...\n✅ Yuborildi: <b>{sent}</b>\n❌ Xato: <b>{failed}</b>\n📌 Tekshirildi: <b>{index}/{len(recipients)}</b>")

    await safe_edit_text(progress, f"✅ <b>Ommaviy xabar yakunlandi</b>\n\n📨 Yuborildi: <b>{sent}</b> ta\n❌ Xato: <b>{failed}</b> ta", reply_markup=back_to_main_kb())
    await state.clear()


@router.callback_query(F.data.startswith("users:page:"))
async def users_pagination(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "users.read"):
        return
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
    if await deny_if_no_permission(call, "users.read"):
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



