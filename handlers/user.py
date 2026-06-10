from .common import *

router = Router()

ADD_RIGHTS = "delete_messages+restrict_members+invite_users+pin_messages"


def add_group_url(bot_username: str) -> str:
    return f"https://t.me/{bot_username}?startgroup=new&admin={ADD_RIGHTS}"


def public_home_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Botni guruhga qo‘shish", url=add_group_url(bot_username))],
        [
            InlineKeyboardButton(text="📖 To‘liq qo‘llanma", callback_data="pub:guide"),
            InlineKeyboardButton(text="🧪 Demo", callback_data="pub:demo"),
        ],
        [
            InlineKeyboardButton(text="🛡 Xavfsizlik testi", callback_data="quiz:start"),
            InlineKeyboardButton(text="❓ FAQ", callback_data="pub:faq"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Imkoniyatlar", callback_data="pub:features"),
            InlineKeyboardButton(text="🆘 Yordam", callback_data="pub:support"),
        ],
    ])


def public_back_kb(bot_username: str, back: str = "pub:home") -> InlineKeyboardMarkup:
    rows = []
    if back != "pub:home":
        rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back)])
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")])
    rows.append([InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=add_group_url(bot_username))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def guide_menu_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Botni qo‘shish", callback_data="guide:add")],
        [InlineKeyboardButton(text="2️⃣ Admin huquqlari", callback_data="guide:rights")],
        [InlineKeyboardButton(text="3️⃣ Panel sozlamalari", callback_data="guide:panel")],
        [InlineKeyboardButton(text="4️⃣ Xavfli fayllar", callback_data="guide:files")],
        [InlineKeyboardButton(text="5️⃣ Tekshirish", callback_data="guide:test")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")],
        [InlineKeyboardButton(text="➕ Hozir guruhga qo‘shish", url=add_group_url(bot_username))],
    ])


def demo_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦠 Zararli fayl misoli", callback_data="demo:file")],
        [InlineKeyboardButton(text="🚫 Yomon so‘z nazorati", callback_data="demo:word")],
        [InlineKeyboardButton(text="🔇 Ogohlantirish va mute", callback_data="demo:mute")],
        [InlineKeyboardButton(text="🔐 Maxfiy guruh logi", callback_data="demo:secret")],
        [InlineKeyboardButton(text="👮 Admin huquqlari", callback_data="demo:admin")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")],
    ])


FAQ_ITEMS = [
    (
        "Bot guruhda ishlashi uchun nima kerak?",
        "Bot guruhga qo‘shilgan va <b>admin</b> qilingan bo‘lishi kerak. Eng kerakli huquqlar: <b>Delete messages</b> va <b>Restrict members</b>. Delete messages bo‘lmasa zararli faylni ko‘radi, lekin o‘chira olmaydi. Restrict members bo‘lmasa qoidabuzarni mute qila olmaydi.",
    ),
    (
        ".apk, .exe, .bat fayllar qanday bloklanadi?",
        "Superadmin paneldan <b>Xavfli fayllar</b> bo‘limiga kirib kengaytmalarni qo‘shadi: <code>.apk</code>, <code>.exe</code>, <code>.bat</code>, <code>.js</code>. Shundan keyin guruhga shu kengaytmadagi fayl tashlansa, bot uni o‘chiradi va logga yozadi.",
    ),
    (
        "photo.jpg.apk nima uchun xavfli?",
        "Bu ikki martalik kengaytma. Foydalanuvchiga rasmdek ko‘rinishi mumkin, lekin aslida APK fayl bo‘lishi mumkin. Bot bunday nomlarni ham aniqlaydi va bloklaydi.",
    ),
    (
        "Maxfiy guruh nima qiladi?",
        "Maxfiy guruh superadminlar uchun nazorat joyi. Zararli fayl ushlansa, bot faylni yoki fayl ma’lumotini maxfiy guruhga yuboradi: kim tashladi, qaysi guruhdan, fayl nomi, sabab va vaqt.",
    ),
    (
        "Maxfiy guruhni qanday ulayman?",
        "Botni maxfiy guruhga admin qiling. Keyin superadmin o‘sha guruh ichida <code>/set_secret_group</code> buyrug‘ini yuboradi. Shundan keyin zararli fayl loglari shu guruhga boradi.",
    ),
    (
        "Adminlarga faqat ko‘rish huquqi bersam nima bo‘ladi?",
        "<b>read</b> faqat ko‘rish uchun. Yangi qo‘shish uchun <b>create</b>, tahrirlash uchun <b>update</b>, o‘chirish uchun <b>delete</b>, maxsus amal uchun <b>action</b> kerak.",
    ),
    (
        "Bot oddiy foydalanuvchilar uchun nimaga kerak?",
        "Oddiy foydalanuvchi botni guruhga qo‘shishi, qo‘llanma o‘qishi, demo ko‘rishi, FAQdan javob olishi va xavfsizlik testidan o‘tishi mumkin.",
    ),
]

QUIZ = [
    {"q": "Sizga noma’lum odam <code>premium.apk</code> yubordi. Nima qilasiz?", "options": ["O‘rnataman", "Avval manbasini tekshiraman, kerak bo‘lmasa ochmayman", "Do‘stlarga ham yuboraman"], "correct": 1, "info": "To‘g‘ri. Noma’lum APK fayllar zararli bo‘lishi mumkin. Manba ishonchli bo‘lmasa ochmang."},
    {"q": "<code>photo.jpg.apk</code> fayli nimani bildirishi mumkin?", "options": ["Oddiy rasm", "Ikki martalik kengaytma orqali yashirilgan APK", "Telegram sticker"], "correct": 1, "info": "To‘g‘ri. Bu rasmdek ko‘rsatishga urinish bo‘lishi mumkin, lekin fayl APK."},
    {"q": "Bot zararli faylni o‘chira olishi uchun qaysi huquq kerak?", "options": ["Delete messages", "Change group info", "Add new admins"], "correct": 0, "info": "To‘g‘ri. Fayl/xabarni o‘chirish uchun Delete messages huquqi kerak."},
    {"q": "Admin faqat read olsa, yangi kengaytma qo‘sha oladimi?", "options": ["Ha", "Yo‘q, create kerak", "Faqat yakshanba kuni"], "correct": 1, "info": "To‘g‘ri. read faqat ko‘rish; qo‘shish uchun create kerak."},
    {"q": "Maxfiy guruhga log borishi uchun nima qilish kerak?", "options": ["Botga /start bosish", "Botni maxfiy guruhga admin qilib /set_secret_group yuborish", "Faqat kanal ochish"], "correct": 1, "info": "To‘g‘ri. Superadmin maxfiy guruhda /set_secret_group yuboradi."},
    {"q": "Qarz so‘ragan akkauntga darhol pul yuborish xavfsizmi?", "options": ["Ha", "Yo‘q, avval telefon orqali shaxsini tasdiqlash kerak", "Faqat kechasi"], "correct": 1, "info": "To‘g‘ri. Akkaunt o‘g‘irlangan bo‘lishi mumkin; avval egasi bilan bog‘laning."},
]


async def send_public_home(message_or_call):
    bot = message_or_call.bot
    bot_username = (await bot.me()).username
    text = (
        "👋 <b>Salom! Men guruhingizni himoya qiluvchi xavfsizlik botiman.</b>\n\n"
        "Men guruhlarda spam, yomon so‘zlar, shubhali fayllar va firibgarlik urinishlarini kamaytirishga yordam beraman.\n\n"
        "🛡 <b>Asosiy imkoniyatlar:</b>\n"
        "• <code>.apk</code>, <code>.exe</code>, <code>.bat</code>, <code>.js</code> kabi xavfli fayllarni bloklash;\n"
        "• <code>photo.jpg.apk</code> kabi yashirin kengaytmalarni aniqlash;\n"
        "• yomon so‘zlarni o‘chirish;\n"
        "• ogohlantirish va avtomatik mute;\n"
        "• superadmin uchun maxfiy log guruhi;\n"
        "• adminlarga aniq CRUD huquqlar berish.\n\n"
        "Boshlash uchun quyidagi tugmalardan foydalaning 👇"
    )
    if isinstance(message_or_call, types.CallbackQuery):
        await safe_edit_text(message_or_call.message, text, reply_markup=public_home_kb(bot_username))
        await message_or_call.answer()
    else:
        await message_or_call.answer(text, reply_markup=public_home_kb(bot_username))


@router.message(Command("start", "panel", "help"))
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
            is_bot_admin,
            "administrator" if is_bot_admin else "member",
        )

        payload = (command.args or "").strip() if command else ""
        if payload.startswith("ref_"):
            await track_referral_chat(payload, message.chat.id)

        await message.answer(
            "✅ <b>Bot guruhda ishga tushdi.</b>\n\n"
            "To‘liq ishlashim uchun meni admin qiling va quyidagi huquqlarni bering:\n"
            "• <b>Delete messages</b> — zararli xabar/fayllarni o‘chirish;\n"
            "• <b>Restrict members</b> — qoidabuzarni vaqtincha cheklash;\n"
            "• <b>Invite users</b> — qo‘shish havolalari uchun.\n\n"
            "Sozlamalar superadmin panelidan boshqariladi."
        )
        return

    if await has_panel_access(message.from_user.id):
        await message.answer("👋 <b>Admin panel</b>\nKerakli bo‘limni tanlang:", reply_markup=await panel_menu_kb(message.from_user.id))
        return

    await send_public_home(message)


@router.callback_query(F.data == "pub:home")
async def public_home(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await send_public_home(call)


@router.callback_query(F.data == "pub:guide")
async def public_guide(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    await safe_edit_text(
        call.message,
        "📖 <b>To‘liq qo‘llanma</b>\n\n"
        "Botni to‘g‘ri ulash va sozlash uchun quyidagi bo‘limlarni ketma-ket o‘qing.\n\n"
        "1️⃣ Botni guruhga qo‘shish\n"
        "2️⃣ Admin huquqlarini berish\n"
        "3️⃣ Paneldan sozlamalarni yoqish\n"
        "4️⃣ Xavfli fayllarni bloklash\n"
        "5️⃣ Test qilib ko‘rish",
        reply_markup=guide_menu_kb(bot_username),
    )
    await call.answer()


@router.callback_query(F.data.startswith("guide:"))
async def guide_detail(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    key = call.data.split(":", 1)[1]
    texts = {
        "add": "1️⃣ <b>Botni guruhga qo‘shish</b>\n\nPastdagi <b>Guruhga qo‘shish</b> tugmasini bosing, kerakli guruhni tanlang va botni qo‘shing. Agar guruh ro‘yxatda chiqmasa, siz u guruhda admin emassiz yoki bot qo‘shish huquqingiz yo‘q.",
        "rights": "2️⃣ <b>Admin huquqlarini berish</b>\n\nBot guruhni himoya qilishi uchun admin bo‘lishi shart. Eng kerakli huquqlar:\n\n• <b>Delete messages</b> — zararli fayl va yomon so‘zlarni o‘chirish;\n• <b>Restrict members</b> — qoidabuzarni mute qilish;\n• <b>Invite users</b> — referral/giper ssilka uchun;\n• <b>Pin messages</b> — kerak bo‘lsa ogohlantirishlarni mahkamlash.",
        "panel": "3️⃣ <b>Panel sozlamalari</b>\n\nSuperadmin shaxsiy chatda /start bosadi va admin panelga kiradi. Paneldan yomon so‘zlar, xavfli fayllar, mute vaqti, ogohlantirish limiti, whitelist va admin huquqlarini boshqaradi.",
        "files": "4️⃣ <b>Xavfli fayllar</b>\n\nPanelda <b>Xavfli fayllar</b> bo‘limiga kiring va kerakli kengaytmalarni qo‘shing:\n<code>.apk</code>, <code>.exe</code>, <code>.bat</code>, <code>.js</code>, <code>.cmd</code>, <code>.scr</code>.\n\nBot ikki martalik kengaytmalarni ham aniqlaydi: <code>rasm.jpg.apk</code>.",
        "test": "5️⃣ <b>Tekshirib ko‘rish</b>\n\n1. Bot guruhda admin ekanini tekshiring.\n2. <code>.apk</code> kengaytmasini panelga qo‘shing.\n3. Guruhga test uchun <code>test.apk</code> nomli fayl yuboring.\n4. Bot faylni o‘chirishi va log yozishi kerak.\n\nAgar o‘chirmasa: Delete messages huquqi, kengaytma ro‘yxati va whitelistni tekshiring.",
    }
    await safe_edit_text(call.message, texts.get(key, "Ma’lumot topilmadi."), reply_markup=public_back_kb(bot_username, "pub:guide"))
    await call.answer()


@router.callback_query(F.data == "pub:demo")
async def public_demo(call: types.CallbackQuery):
    await safe_edit_text(call.message, "🧪 <b>Demo</b>\n\nBot qanday ishlashini misollar orqali ko‘ring.", reply_markup=demo_menu_kb())
    await call.answer()


@router.callback_query(F.data.startswith("demo:"))
async def demo_detail(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    key = call.data.split(":", 1)[1]
    texts = {
        "file": "🦠 <b>Zararli fayl misoli</b>\n\nFoydalanuvchi guruhga <code>game.apk</code> yubordi. Agar <code>.apk</code> xavfli ro‘yxatda bo‘lsa:\n\n1. bot faylni aniqlaydi;\n2. maxfiy guruhga ma’lumot yuboradi;\n3. asl guruhdan faylni o‘chiradi;\n4. logga yozadi.",
        "word": "🚫 <b>Yomon so‘z nazorati</b>\n\nTaqiqlangan so‘zlar paneldan qo‘shiladi. Kimdir shu so‘zni yozsa, bot xabarni o‘chiradi, foydalanuvchiga ogohlantirish beradi va log yozadi.",
        "mute": "🔇 <b>Ogohlantirish va mute</b>\n\nMasalan limit 3 bo‘lsa, foydalanuvchi 3-marta qoida buzganida vaqtincha yozishdan cheklanadi. Mute vaqti paneldan belgilanadi.",
        "secret": "🔐 <b>Maxfiy guruh logi</b>\n\nSuperadmin maxfiy guruhni ulaydi. Shundan keyin zararli fayl ushlansa, bot maxfiy guruhga kim tashlagani, qaysi guruhdanligi, fayl nomi va sababini yuboradi.",
        "admin": "👮 <b>Admin huquqlari</b>\n\nSuperadmin adminlarga faqat kerakli CRUD huquqlarni beradi. Masalan admin faqat <b>read</b> olsa, ko‘radi, lekin yaratmaydi. Yaratish uchun <b>create</b> kerak.",
    }
    await safe_edit_text(call.message, texts.get(key, "Demo topilmadi."), reply_markup=public_back_kb(bot_username, "pub:demo"))
    await call.answer()


@router.callback_query(F.data == "pub:features")
async def public_features(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    await safe_edit_text(
        call.message,
        "⚙️ <b>Bot imkoniyatlari</b>\n\n"
        "🛡 <b>Guruh himoyasi:</b> yomon so‘zlar, xavfli fayllar, ikki martalik kengaytma, katta fayl va arxiv nazorati.\n\n"
        "👮 <b>Admin panel:</b> superadmin, adminlar, rollar, CRUD huquqlar, vaqtinchalik admin, audit log.\n\n"
        "🔐 <b>Monitoring:</b> maxfiy guruhga zararli fayl haqida xabar va batafsil log.\n\n"
        "📢 <b>Ommaviy xabar:</b> foydalanuvchilar, guruhlar yoki hammaga format saqlangan holda yuborish.",
        reply_markup=public_back_kb(bot_username),
    )
    await call.answer()


@router.callback_query(F.data == "pub:support")
async def public_support(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    await safe_edit_text(
        call.message,
        "🆘 <b>Yordam</b>\n\n"
        "Agar bot ishlamasa, quyidagilarni tekshiring:\n\n"
        "1. Bot guruhda adminmi?\n"
        "2. Delete messages huquqi bormi?\n"
        "3. Xavfli kengaytma panelga qo‘shilganmi?\n"
        "4. Fayl tashlagan odam whitelistda emasmi?\n"
        "5. Bot serverda ishlab turibdimi?\n"
        "6. Maxfiy guruh ulanganmi?\n\n"
        "Ko‘p uchraydigan xato: Telegram network timeout. Bunda fayl maxfiy guruhga yuborilmasligi mumkin, lekin kod faylni guruhdan baribir o‘chirishi kerak.",
        reply_markup=public_back_kb(bot_username),
    )
    await call.answer()


@router.callback_query(F.data == "pub:faq")
async def public_faq(call: types.CallbackQuery):
    rows = [[InlineKeyboardButton(text=f"{i+1}. {q[:48]}", callback_data=f"faq:{i}")] for i, (q, _) in enumerate(FAQ_ITEMS)]
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")])
    await safe_edit_text(call.message, "❓ <b>FAQ — ko‘p so‘raladigan savollar</b>\n\nSavolni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("faq:"))
async def faq_detail(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    try:
        idx = int(call.data.split(":", 1)[1])
        q, a = FAQ_ITEMS[idx]
    except Exception:
        return await call.answer("Savol topilmadi.", show_alert=True)
    await safe_edit_text(call.message, f"❓ <b>{escape(q)}</b>\n\n{a}", reply_markup=public_back_kb(bot_username, "pub:faq"))
    await call.answer()


@router.callback_query(F.data == "quiz:start")
async def quiz_start(call: types.CallbackQuery):
    await show_quiz_question(call, 0, 0)


async def show_quiz_question(call: types.CallbackQuery, index: int, score: int):
    bot_username = (await call.bot.me()).username
    if index >= len(QUIZ):
        level = "A’lo" if score >= 5 else "Yaxshi" if score >= 4 else "Boshlang‘ich"
        await safe_edit_text(
            call.message,
            "🏁 <b>Xavfsizlik testi yakunlandi</b>\n\n"
            f"Natija: <b>{score}/{len(QUIZ)}</b>\n"
            f"Daraja: <b>{level}</b>\n\n"
            "Qo‘llanmani o‘qib, testni qayta ishlasangiz xavfsizlik bilimlaringiz yanada oshadi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Qayta test", callback_data="quiz:start")],
                [InlineKeyboardButton(text="📖 Qo‘llanma", callback_data="pub:guide")],
                [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")],
                [InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=add_group_url(bot_username))],
            ]),
        )
        await call.answer()
        return

    item = QUIZ[index]
    rows = [[InlineKeyboardButton(text=opt[:60], callback_data=f"quiz:ans:{index}:{score}:{i}")] for i, opt in enumerate(item["options"])]
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")])
    await safe_edit_text(call.message, f"🛡 <b>Xavfsizlik testi</b>\nSavol <b>{index+1}/{len(QUIZ)}</b>\n\n{item['q']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await call.answer()


@router.callback_query(F.data.startswith("quiz:ans:"))
async def quiz_answer(call: types.CallbackQuery):
    _, _, index_s, score_s, answer_s = call.data.split(":")
    index = int(index_s)
    score = int(score_s)
    answer = int(answer_s)
    item = QUIZ[index]
    correct = answer == item["correct"]
    new_score = score + (1 if correct else 0)
    await safe_edit_text(
        call.message,
        ("✅ <b>To‘g‘ri!</b>\n\n" if correct else "❌ <b>Noto‘g‘ri.</b>\n\n") + item["info"],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Keyingi savol", callback_data=f"quiz:next:{index+1}:{new_score}")],
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")],
        ]),
    )
    await call.answer()


@router.callback_query(F.data.startswith("quiz:next:"))
async def quiz_next(call: types.CallbackQuery):
    _, _, index_s, score_s = call.data.split(":")
    await show_quiz_question(call, int(index_s), int(score_s))
