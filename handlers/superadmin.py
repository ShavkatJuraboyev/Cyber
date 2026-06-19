from .common import *
from utils.timezone import format_samarkand

router = Router()

def panel_admins_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo‘shish", callback_data="pa:add")],
        [InlineKeyboardButton(text="📋 Adminlar ro‘yxati", callback_data="pa:list")],
        [InlineKeyboardButton(text="🎭 Rollar / CRUD huquqlar", callback_data="role:list")],
        [InlineKeyboardButton(text="⚡ Role template", callback_data="role:templates")],
        [InlineKeyboardButton(text="🧾 Admin audit log", callback_data="pa:audit")],
        [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")],
    ])


def permission_buttons(user_id: int, allowed: set[str]) -> InlineKeyboardMarkup:
    rows = []
    rows.append([InlineKeyboardButton(text="👁 Huquqlar preview", callback_data=f"pa:preview:{user_id}")])
    rows.append([InlineKeyboardButton(text="⏳ Muddat berish", callback_data=f"pa:expiry:{user_id}")])
    rows.append([InlineKeyboardButton(text="🎭 Rollarni biriktirish", callback_data=f"pa:roles:{user_id}")])
    for module, module_label in PANEL_MODULES.items():
        rows.append([InlineKeyboardButton(text=f"— {module_label} —", callback_data="noop")])
        row = []
        for action, action_label in CRUD_ACTIONS.items():
            perm = f"{module}.{action}"
            mark = "✅" if perm in allowed else "❌"
            short = action_label.split(" ", 1)[0]
            row.append(InlineKeyboardButton(text=f"{mark}{short}", callback_data=f"pa:perm:{user_id}:{perm}"))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="🗑 Adminni o‘chirish", callback_data=f"pa:delete:{user_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Adminlar ro‘yxati", callback_data="pa:list")])
    rows.append([InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def role_permission_buttons(role_id: int, allowed: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for module, module_label in PANEL_MODULES.items():
        rows.append([InlineKeyboardButton(text=f"— {module_label} —", callback_data="noop")])
        row = []
        for action, action_label in CRUD_ACTIONS.items():
            perm = f"{module}.{action}"
            mark = "✅" if perm in allowed else "❌"
            short = action_label.split(" ", 1)[0]
            row.append(InlineKeyboardButton(text=f"{mark}{short}", callback_data=f"role:perm:{role_id}:{perm}"))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
    rows.append([InlineKeyboardButton(text="✏️ Rol nomini tahrirlash", callback_data=f"role:edit:{role_id}")])
    rows.append([InlineKeyboardButton(text="🗑 Rolni o‘chirish", callback_data=f"role:delete:{role_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Rollar", callback_data="role:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "pa:menu")
async def panel_admin_menu(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Bu bo‘lim faqat SUPERADMIN uchun.", show_alert=True)
    await state.clear()
    await call.message.edit_text(
        "👮 <b>Bot adminlari</b>\n\n"
        "Bu bo‘limda .env dagi SUPERADMIN boshqa adminlarni qo‘shadi va ularga huquq beradi.",
        reply_markup=panel_admins_menu_kb()
    )
    await call.answer()


@router.callback_query(F.data == "pa:add")
async def panel_admin_add_start(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    await state.set_state(PanelAdminStates.add_admin)
    await call.message.edit_text(
        "Yangi adminning Telegram ID raqamini yuboring.\n\n"
        "Masalan: <code>123456789</code>",
        reply_markup=panel_admins_menu_kb()
    )
    await call.answer()


@router.message(PanelAdminStates.add_admin, F.text.regexp(r"^\d+$"))
async def panel_admin_add_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    user_id = int(message.text.strip())
    if is_super_admin(user_id):
        await message.answer("ℹ️ Bu foydalanuvchi allaqachon .env ichida SUPERADMIN.", reply_markup=panel_admins_menu_kb())
        await state.clear()
        return
    known = await get_user_by_id(user_id)
    full_name = ""
    username = ""
    if known:
        full_name = f"{known[1] or ''} {known[2] or ''}".strip()
        username = known[3] or ""
    await add_panel_admin(user_id, full_name, username, message.from_user.id)
    await add_admin_audit_log(message.from_user.id, user_id, "admin_add", "Yangi admin qo‘shildi")
    # Boshlang‘ich huquq: hech narsa emas. Superadmin o‘zi yoqadi.
    await message.answer(
        f"✅ <code>{user_id}</code> admin qilib qo‘shildi.\n"
        "Endi ro‘yxatdan kirib, kerakli huquqlarni yoqing.",
        reply_markup=panel_admins_menu_kb()
    )
    await state.clear()


@router.callback_query(F.data == "pa:list")
async def panel_admin_list(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    admins = await list_panel_admins()
    if not admins:
        await call.message.edit_text("📋 Hozircha bot admin qo‘shilmagan.", reply_markup=panel_admins_menu_kb())
        return await call.answer()
    text = "📋 <b>Bot adminlari</b>\n\n"
    rows = []
    for row in admins:
        user_id, full_name, username, is_active, created_by, created_at = row[:6]
        expires_at = row[6] if len(row) > 6 else None
        allowed = await get_admin_effective_permissions(user_id)
        name = full_name or ("@" + username if username else str(user_id))
        text += f"• <b>{escape(name)}</b> — <code>{user_id}</code> | huquqlar: <b>{len(allowed)}</b>" + (f" | muddat: <code>{escape(str(expires_at))}</code>" if expires_at else "") + "\n"
        rows.append([InlineKeyboardButton(text=f"👮 {name[:40]} ({user_id})", callback_data=f"pa:detail:{user_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="pa:menu")])
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("pa:detail:"))
async def panel_admin_detail(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    admin = await get_panel_admin(user_id)
    if not admin:
        return await call.answer("❌ Admin topilmadi.", show_alert=True)
    allowed = await get_panel_admin_permissions(user_id)
    name = admin[1] or ("@" + admin[2] if admin[2] else str(user_id))
    text = (
        f"👮 <b>{escape(name)}</b>\n"
        f"ID: <code>{user_id}</code>\n\n"
        "Quyidagi huquqlarni yoqib/o‘chiring:\n"
    )
    await call.message.edit_text(text, reply_markup=permission_buttons(user_id, allowed))
    await call.answer()


@router.callback_query(F.data.startswith("pa:perm:"))
async def panel_admin_toggle_permission(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    _, _, user_id_s, perm = call.data.split(":", 3)
    user_id = int(user_id_s)
    if perm not in PANEL_PERMISSIONS:
        return await call.answer("❌ Noma’lum huquq.", show_alert=True)
    allowed = await get_panel_admin_permissions(user_id)
    new_value = perm not in allowed
    await set_panel_admin_permission(user_id, perm, new_value)
    await add_admin_audit_log(call.from_user.id, user_id, "permission_on" if new_value else "permission_off", perm)

    # Agar huquq o‘chirilgandan keyin adminning direct + role huquqlari 0 ta bo‘lsa,
    # panel_admins jadvalidan olib tashlaymiz. Shunda /start bosganda oddiy foydalanuvchi menyusi chiqadi.
    if not new_value and await demote_panel_admin_if_empty(user_id):
        await call.answer("❌ Barcha huquqlar olib tashlandi. Admin oddiy foydalanuvchiga aylantirildi.", show_alert=True)
        await panel_admin_list(call)
        return

    allowed = await get_panel_admin_permissions(user_id)
    await call.message.edit_reply_markup(reply_markup=permission_buttons(user_id, allowed))
    await call.answer("✅ Huquq yoqildi" if new_value else "❌ Huquq o‘chirildi")


@router.callback_query(F.data.startswith("pa:delete:"))
async def panel_admin_delete_ask(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    await call.message.edit_text(
        f"⚠️ <code>{user_id}</code> adminni o‘chirishni tasdiqlaysizmi?",
        reply_markup=confirm_kb(f"pa:delete_confirm:{user_id}", f"pa:detail:{user_id}")
    )
    await call.answer()


@router.callback_query(F.data.startswith("pa:delete_confirm:"))
async def panel_admin_delete(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    deleted = await remove_panel_admin(user_id)
    await add_admin_audit_log(call.from_user.id, user_id, "admin_delete", "Admin o‘chirildi" if deleted else "Admin topilmadi")
    await call.answer("✅ Admin o‘chirildi" if deleted else "❌ Topilmadi", show_alert=True)
    await panel_admin_list(call)


@router.callback_query(F.data == "role:list")
async def role_list_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Bu bo‘lim faqat SUPERADMIN uchun.", show_alert=True)
    roles = await list_panel_roles()
    text = "🎭 <b>Rollar / CRUD huquqlar</b>\n\nRol yarating, keyin rolega har bir amal bo‘yicha huquq bering. Keyin adminni shu rolega biriktirasiz.\n\n"
    rows = [[InlineKeyboardButton(text="➕ Yangi rol yaratish", callback_data="role:create")]]
    if roles:
        for role_id, name, desc, created_by, created_at in roles:
            text += f"• <b>{escape(name)}</b> — <code>ID:{role_id}</code>\n"
            rows.append([InlineKeyboardButton(text=f"🎭 {name[:45]}", callback_data=f"role:detail:{role_id}")])
    else:
        text += "Hozircha rol yo‘q.\n"
    rows.append([InlineKeyboardButton(text="⬅️ Adminlar", callback_data="pa:menu")])
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data == "role:create")
async def role_create_start(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    await state.set_state(PanelAdminStates.create_role)
    await call.message.edit_text(
        "Yangi rol nomini yuboring.\n\nMasalan: <code>Moderator</code>, <code>Referral manager</code>, <code>Read only</code>",
        reply_markup=panel_admins_menu_kb()
    )
    await call.answer()


@router.message(PanelAdminStates.create_role)
async def role_create_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        return await message.answer("❌ Rol nomi juda qisqa.")
    role_id = await create_panel_role(name, "", message.from_user.id)
    await state.clear()
    await message.answer(f"✅ <b>{escape(name)}</b> roli yaratildi. Endi CRUD huquqlarni yoqing.")
    allowed = await get_panel_role_permissions(role_id)
    await message.answer("🎭 Rol huquqlari:", reply_markup=role_permission_buttons(role_id, allowed))


@router.callback_query(F.data.startswith("role:detail:"))
async def role_detail_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    role_id = int(call.data.split(":")[2])
    role = await get_panel_role(role_id)
    if not role:
        return await call.answer("❌ Rol topilmadi.", show_alert=True)
    allowed = await get_panel_role_permissions(role_id)
    text = (
        f"🎭 <b>{escape(role[1])}</b>\n"
        f"ID: <code>{role_id}</code>\n"
        f"Huquqlar soni: <b>{len(allowed)}</b>\n\n"
        "CRUD huquqlarni yoqing/o‘chiring:\n"
        "👁=read, ➕=create, ✏️=update, 🗑=delete, ⚙️=action"
    )
    await call.message.edit_text(text, reply_markup=role_permission_buttons(role_id, allowed))
    await call.answer()


@router.callback_query(F.data.startswith("role:perm:"))
async def role_permission_toggle(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    _, _, role_id_s, perm = call.data.split(":", 3)
    role_id = int(role_id_s)
    if perm not in PANEL_PERMISSIONS:
        return await call.answer("❌ Noma’lum permission.", show_alert=True)
    allowed = await get_panel_role_permissions(role_id)
    new_value = perm not in allowed
    await set_panel_role_permission(role_id, perm, new_value)
    allowed = await get_panel_role_permissions(role_id)
    try:
        await call.message.edit_reply_markup(reply_markup=role_permission_buttons(role_id, allowed))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await call.answer("✅ Yoqildi" if new_value else "❌ O‘chirildi")


@router.callback_query(F.data.startswith("role:delete:"))
async def role_delete_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    role_id = int(call.data.split(":")[2])
    ok = await delete_panel_role(role_id)
    await call.answer("✅ Rol o‘chirildi" if ok else "❌ Rol topilmadi", show_alert=True)
    await role_list_handler(call)


@router.callback_query(F.data.startswith("role:edit:"))
async def role_edit_start(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    role_id = int(call.data.split(":")[2])
    role = await get_panel_role(role_id)
    if not role:
        return await call.answer("❌ Rol topilmadi.", show_alert=True)
    await state.update_data(edit_role_id=role_id)
    await state.set_state(PanelAdminStates.edit_role_name)
    await call.message.edit_text(f"Rol uchun yangi nom yuboring.\nHozirgi nom: <b>{escape(role[1])}</b>", reply_markup=panel_admins_menu_kb())
    await call.answer()


@router.message(PanelAdminStates.edit_role_name)
async def role_edit_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    data = await state.get_data()
    role_id = int(data.get("edit_role_id"))
    name = (message.text or "").strip()
    if len(name) < 2:
        return await message.answer("❌ Rol nomi juda qisqa.")
    ok = await update_panel_role(role_id, name, "")
    await state.clear()
    await message.answer("✅ Rol tahrirlandi." if ok else "❌ Rol topilmadi.", reply_markup=panel_admins_menu_kb())


@router.callback_query(F.data.startswith("pa:roles:"))
async def admin_roles_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    admin = await get_panel_admin(user_id)
    if not admin:
        return await call.answer("❌ Admin topilmadi.", show_alert=True)
    all_roles = await list_panel_roles()
    admin_roles = await get_admin_roles(user_id)
    admin_role_ids = {r[0] for r in admin_roles}
    text = f"🎭 <b>{user_id}</b> adminiga role biriktirish\n\n"
    if admin_roles:
        text += "Biriktirilgan rollar:\n" + "\n".join(f"• {escape(r[1])}" for r in admin_roles) + "\n\n"
    else:
        text += "Hozircha rol biriktirilmagan.\n\n"
    rows = []
    for role_id, name, desc, created_by, created_at in all_roles:
        mark = "✅" if role_id in admin_role_ids else "❌"
        rows.append([InlineKeyboardButton(text=f"{mark} {name[:45]}", callback_data=f"pa:role_toggle:{user_id}:{role_id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Admin detali", callback_data=f"pa:detail:{user_id}")])
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("pa:role_toggle:"))
async def admin_role_toggle_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    _, _, user_id_s, role_id_s = call.data.split(":", 3)
    user_id = int(user_id_s)
    role_id = int(role_id_s)
    current = {r[0] for r in await get_admin_roles(user_id)}
    if role_id in current:
        await remove_role_from_admin(user_id, role_id)
        if await demote_panel_admin_if_empty(user_id):
            await call.answer("❌ Rol olib tashlandi. Huquqlar qolmagani uchun admin oddiy foydalanuvchiga aylantirildi.", show_alert=True)
            await panel_admin_list(call)
            return
        await call.answer("❌ Rol olib tashlandi")
    else:
        await assign_role_to_admin(user_id, role_id, call.from_user.id)
        await add_admin_audit_log(call.from_user.id, user_id, "role_assigned", str(role_id))
        await call.answer("✅ Rol biriktirildi")
    await admin_roles_handler(call)


@router.callback_query(F.data == "noop")
async def noop_handler(call: types.CallbackQuery):
    await call.answer("Bu bo‘lim uchun huquq berilmagan.", show_alert=True)





@router.callback_query(F.data.startswith("pa:preview:"))
async def panel_admin_permission_preview(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    perms = await get_admin_effective_permissions(user_id)
    roles = await get_admin_roles(user_id)
    text = f"👁 <b>{user_id}</b> adminining effective huquqlari\n\n"
    if roles:
        text += "🎭 Rollari: " + ", ".join(escape(r[1]) for r in roles) + "\n\n"
    text += format_permission_preview(perms)
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Admin detali", callback_data=f"pa:detail:{user_id}")]
    ]))
    await call.answer()


@router.callback_query(F.data.startswith("pa:expiry:"))
async def panel_admin_expiry_start(call: types.CallbackQuery, state: FSMContext):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    user_id = int(call.data.split(":")[2])
    await state.update_data(expiry_user_id=user_id)
    await state.set_state(PanelAdminStates.set_expiry)
    await call.message.edit_text(
        "Admin necha kunga faol bo‘lsin?\n\nMasalan: <code>7</code>. Cheksiz qilish uchun <code>0</code> yuboring.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Admin detali", callback_data=f"pa:detail:{user_id}")]])
    )
    await call.answer()


@router.message(PanelAdminStates.set_expiry, F.text.regexp(r"^\d{1,4}$"))
async def panel_admin_expiry_finish(message: types.Message, state: FSMContext):
    if not is_super_admin(message.from_user.id):
        return
    data = await state.get_data()
    user_id = int(data.get("expiry_user_id"))
    days = int(message.text.strip())
    await set_panel_admin_expiry(user_id, days if days > 0 else None)
    await add_admin_audit_log(message.from_user.id, user_id, "expiry_set", f"{days} kun" if days > 0 else "cheksiz")
    await state.clear()
    await message.answer("✅ Admin muddati yangilandi." if days > 0 else "✅ Admin muddati cheksiz qilindi.", reply_markup=panel_admins_menu_kb())


@router.callback_query(F.data == "pa:audit")
async def panel_admin_audit(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    rows = await get_admin_audit_logs(30)
    text = "🧾 <b>Admin audit log</b>\n\n"
    if not rows:
        text += "Hozircha yozuv yo‘q."
    else:
        for actor_id, target_user_id, action, details, created_at in rows:
            text += f"• <b>{escape(action)}</b> | actor: <code>{actor_id}</code> | target: <code>{target_user_id}</code>\n  {escape(details or '—')} | <code>{format_samarkand(created_at)}</code>\n\n"
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Adminlar", callback_data="pa:menu")]]))
    await call.answer()


@router.callback_query(F.data == "role:templates")
async def role_templates_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    rows = [[InlineKeyboardButton(text=f"⚡ {v['name']}", callback_data=f"role:template:{k}")] for k, v in ROLE_TEMPLATES.items()]
    rows.append([InlineKeyboardButton(text="⬅️ Adminlar", callback_data="pa:menu")])
    await call.message.edit_text("⚡ Qaysi tayyor rolni yaratamiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("role:template:"))
async def role_template_create_handler(call: types.CallbackQuery):
    if not is_super_admin(call.from_user.id):
        return await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
    key = call.data.split(":", 2)[2]
    tpl = ROLE_TEMPLATES.get(key)
    if not tpl:
        return await call.answer("❌ Template topilmadi.", show_alert=True)
    role_id = await create_panel_role(tpl["name"], "Auto template", call.from_user.id)
    for perm in tpl["perms"]:
        if perm in PANEL_PERMISSIONS:
            await set_panel_role_permission(role_id, perm, True)
    await add_admin_audit_log(call.from_user.id, None, "role_template_created", tpl["name"])
    allowed = await get_panel_role_permissions(role_id)
    await call.answer("✅ Template rol yaratildi", show_alert=True)
    await call.message.edit_text(f"✅ <b>{escape(tpl['name'])}</b> template roli yaratildi.", reply_markup=role_permission_buttons(role_id, allowed))


@router.callback_query(F.data == "secret:menu")
async def secret_log_menu(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "secret_logs.read"):
        return
    rows = await list_private_log_chats()
    text = "🔐 <b>Maxfiy guruhlar</b>\n\n"
    if rows:
        text += f"Jami maxfiy guruh: <b>{len(rows)}</b>\n\n"
        for i, row in enumerate(rows, start=1):
            chat_id, title, chat_type, added_by, added_at = row
            text += (
                f"{i}. <b>{escape(title or str(chat_id))}</b>\n"
                f"   ID: <code>{chat_id}</code> | Turi: <code>{escape(chat_type or '—')}</code>\n"
                f"   Qo‘shgan: <code>{added_by or '—'}</code> | {format_samarkand(added_at)}\n\n"
            )
    else:
        text += "Hali maxfiy guruh tanlanmagan.\n\n"
    text += "Yangi maxfiy guruh qo‘shish uchun bot admin bo‘lgan guruh ichida superadmin <code>/set_secret_group</code> yuboradi. Bir nechta guruh qo‘shish mumkin."

    kb_rows = []
    for row in rows[:20]:
        chat_id, title, *_ = row
        kb_rows.append([InlineKeyboardButton(text=f"🗑 {str(title or chat_id)[:35]}", callback_data=f"secret:remove:{chat_id}")])
    if rows:
        kb_rows.append([InlineKeyboardButton(text="🧹 Hammasini tozalash", callback_data="secret:clear")])
    kb_rows.append([InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="menu:main")])
    await call.message.edit_text(text[:3900], reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()


@router.callback_query(F.data == "secret:clear")
async def secret_log_clear(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "secret_logs.update"):
        return
    await clear_private_log_chats()
    await call.answer("✅ Barcha maxfiy guruhlar o‘chirildi", show_alert=True)
    await secret_log_menu(call)


@router.callback_query(F.data.startswith("secret:remove:"))
async def secret_log_remove(call: types.CallbackQuery):
    if await deny_if_no_permission(call, "secret_logs.update"):
        return
    chat_id = int(call.data.split(":")[2])
    await remove_private_log_chat(chat_id)
    await call.answer("✅ Maxfiy guruh ro‘yxatdan o‘chirildi", show_alert=True)
    await secret_log_menu(call)


@router.message(Command("set_secret_group"))
async def set_secret_group_cmd(message: types.Message):
    if not is_super_admin(message.from_user.id if message.from_user else None):
        return
    if message.chat.type not in {"group", "supergroup"}:
        return await message.answer("Bu komandani maxfiy guruh ichida yuboring.")
    try:
        bot_member = await message.bot.get_chat_member(message.chat.id, (await message.bot.me()).id)
        if bot_member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
            return await message.answer("Avval botni shu maxfiy guruhda admin qiling.")
    except Exception:
        return await message.answer("Bot statusini tekshirib bo‘lmadi.")
    title = message.chat.title or "Maxfiy guruh"
    await add_private_log_chat(message.chat.id, title, message.chat.type, message.from_user.id if message.from_user else None)
    await add_or_update_chat(message.chat.id, title, message.chat.type, await get_chat_link(message.chat), 1, "administrator")
    await message.answer(f"✅ Maxfiy guruh qo‘shildi: <b>{escape(title)}</b>\nID: <code>{message.chat.id}</code>")
