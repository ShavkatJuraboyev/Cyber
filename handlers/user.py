from .common import *
from urllib.parse import quote

router = Router()

ADD_RIGHTS = "delete_messages+restrict_members+invite_users+pin_messages"


def add_group_url(bot_username: str, ref_code: str | None = None) -> str:
    """Botni guruh/superguruhga admin qilib qo‘shish uchun direct deep-link."""
    payload = ref_code or "new"
    return f"https://t.me/{bot_username}?startgroup={payload}&admin={ADD_RIGHTS}"


def add_channel_url(bot_username: str, ref_code: str | None = None) -> str:
    """Botni kanalga admin qilib qo‘shish uchun direct deep-link."""
    payload = ref_code or "new"
    return f"https://t.me/{bot_username}?startchannel={payload}&admin={ADD_RIGHTS}"


def referral_share_url(bot_username: str, ref_code: str | None = None) -> str | None:
    if not ref_code:
        return None
    public_url = f"https://t.me/{bot_username}?start={ref_code}"
    text = "Botni guruhga admin qilib qo‘shish uchun shu havolani bosing."
    return f"https://t.me/share/url?url={quote(public_url)}&text={quote(text)}"


def public_home_kb(bot_username: str, ref_code: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=add_group_url(bot_username, ref_code))],
        [InlineKeyboardButton(text="📢 Kanalga qo‘shish", url=add_channel_url(bot_username, ref_code))],
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
    ]
    share_url = referral_share_url(bot_username, ref_code)
    if share_url:
        rows.insert(2, [InlineKeyboardButton(text="🔗 Shu ssilkani ulashish", url=share_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def public_back_kb(bot_username: str, back: str = "pub:home", ref_code: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if back != "pub:home":
        rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back)])
    rows.append([InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")])
    rows.append([InlineKeyboardButton(text="➕ Guruhga qo‘shish", url=add_group_url(bot_username, ref_code))])
    rows.append([InlineKeyboardButton(text="📢 Kanalga qo‘shish", url=add_channel_url(bot_username, ref_code))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def guide_menu_kb(bot_username: str, ref_code: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Botni qo‘shish", callback_data="guide:add")],
        # [InlineKeyboardButton(text="2️⃣ Admin huquqlari", callback_data="guide:rights")],
        # [InlineKeyboardButton(text="3️⃣ Panel sozlamalari", callback_data="guide:panel")],
        # [InlineKeyboardButton(text="4️⃣ Xavfli fayllar", callback_data="guide:files")],
        # [InlineKeyboardButton(text="5️⃣ Tekshirish", callback_data="guide:test")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")],
        [InlineKeyboardButton(text="➕ Hozir guruhga qo‘shish", url=add_group_url(bot_username, ref_code))],
        [InlineKeyboardButton(text="📢 Hozir kanalga qo‘shish", url=add_channel_url(bot_username, ref_code))],
    ])


def demo_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🦠 Zararli fayl misoli", callback_data="demo:file")],
        [InlineKeyboardButton(text="🚫 Yomon so‘z nazorati", callback_data="demo:word")],
        [InlineKeyboardButton(text="🔇 Ogohlantirish va mute", callback_data="demo:mute")],
        # [InlineKeyboardButton(text="🔐 Maxfiy guruh logi", callback_data="demo:secret")],
        # [InlineKeyboardButton(text="👮 Admin huquqlari", callback_data="demo:admin")],
        [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="pub:home")],
    ])


FAQ_ITEMS = [
    (
        "Bot guruhda ishlashi uchun nima qilish kerak?",
        "Botni guruhga qo‘shing va guruh sozlamalarida administrator qiling. Shundan so‘ng bot guruh xavfsizligini kuzatishga yordam beradi.",
    ),
    (
        "Bot qanday himoya qiladi?",
        "Bot shubhali fayllar, nomaqbul so‘zlar, xavfli ko‘rinadigan xabarlar va firibgarlik urinishlarini kamaytirishga yordam beradi.",
    ),
    (
        ".apk, .exe va .bat fayllar nima uchun xavfli?",
        "Bunday fayllar qurilmada dastur ishga tushirishi mumkin. Manbasi ishonchli bo‘lmasa, ularni yuklab olish yoki ochish tavsiya etilmaydi.",
    ),
    (
        "photo.jpg.apk nima uchun shubhali?",
        "Bu fayl nomi rasmga o‘xshab ko‘rinishi mumkin, lekin oxiridagi .apk uning dastur fayli bo‘lishi mumkinligini bildiradi.",
    ),
    (
        "Noma’lum havolani ochish xavfsizmi?",
        "Yo‘q. Avval havolaning manbasini tekshiring. Shubhali havolalar soxta sayt, firibgarlik yoki zararli sahifaga olib borishi mumkin.",
    ),
    (
        "Kuchli parol qanday bo‘lishi kerak?",
        "Kuchli parol katta va kichik harflar, raqamlar hamda maxsus belgilar aralashmasidan iborat bo‘lgani yaxshi.",
    ),
    (
        "Ikki bosqichli himoya nima uchun kerak?",
        "Ikki bosqichli himoya akkauntingizga qo‘shimcha xavfsizlik beradi. Parolingiz bilinib qolsa ham, begona odam kirishi qiyinlashadi.",
    ),
    (
        "Bot foydalanuvchilar uchun nimaga kerak?",
        "Bot orqali xavfsizlik bo‘yicha qo‘llanma o‘qish, misollarni ko‘rish va qisqa test orqali bilimni tekshirish mumkin.",
    ),
]

QUIZ = [
    {
        "q": "Sizga noma’lum odam <code>premium.apk</code> yubordi. Nima qilasiz?",
        "options": [
            "O‘rnataman",
            "Avval manbasini tekshiraman, kerak bo‘lmasa ochmayman",
            "Do‘stlarga ham yuboraman"
        ],
        "correct": 1,
        "info": "To‘g‘ri. Noma’lum APK fayllar zararli bo‘lishi mumkin. Manba ishonchli bo‘lmasa ochmang."
    },
    {
        "q": "<code>photo.jpg.apk</code> fayli nimani bildirishi mumkin?",
        "options": [
            "Oddiy rasm",
            "Ikki martalik kengaytma orqali yashirilgan APK",
            "Telegram sticker"
        ],
        "correct": 1,
        "info": "To‘g‘ri. Bu rasmdek ko‘rsatishga urinish bo‘lishi mumkin, lekin aslida APK fayl."
    },
    {
        "q": "Bot zararli faylni o‘chira olishi uchun qaysi huquq kerak?",
        "options": [
            "Delete messages",
            "Change group info",
            "Add new admins"
        ],
        "correct": 0,
        "info": "To‘g‘ri. Fayl yoki xabarni o‘chirish uchun Delete messages huquqi kerak."
    },
    {
        "q": "Qarz so‘ragan akkauntga darhol pul yuborish xavfsizmi?",
        "options": [
            "Ha",
            "Yo‘q, avval telefon orqali shaxsini tasdiqlash kerak",
            "Faqat kechasi"
        ],
        "correct": 1,
        "info": "To‘g‘ri. Akkaunt o‘g‘irlangan bo‘lishi mumkin, avval egasi bilan bog‘laning."
    },
    {
        "q": "Notanish havolani bosishdan oldin nima qilish kerak?",
        "options": [
            "Darhol ochish",
            "Havola manzilini tekshirish",
            "Barchaga yuborish"
        ],
        "correct": 1,
        "info": "To‘g‘ri. Havola qayerga olib borishini tekshirib ko‘rish kerak."
    },
    {
        "q": "Kuchli parol qanday bo‘lishi kerak?",
        "options": [
            "12345678",
            "Tug‘ilgan sana",
            "Harflar, raqamlar va belgilar aralashmasi"
        ],
        "correct": 2,
        "info": "To‘g‘ri. Kuchli parol turli belgilar kombinatsiyasidan iborat bo‘ladi."
    },
    {
        "q": "Bir xil parolni barcha akkauntlarda ishlatish xavfsizmi?",
        "options": [
            "Ha",
            "Yo‘q",
            "Faqat Telegram uchun mumkin"
        ],
        "correct": 1,
        "info": "To‘g‘ri. Bitta akkaunt buzilsa, qolganlari ham xavf ostida qoladi."
    },
    {
        "q": "Ikki bosqichli himoya (2FA) nima uchun kerak?",
        "options": [
            "Internetni tezlashtirish uchun",
            "Akkaunt xavfsizligini oshirish uchun",
            "Rasm yuborish uchun"
        ],
        "correct": 1,
        "info": "To‘g‘ri. 2FA akkauntga qo‘shimcha himoya qatlamini qo‘shadi."
    },
    {
        "q": "Bank kartangiz ma'lumotlarini begona odamga yuborish xavfsizmi?",
        "options": [
            "Ha",
            "Yo‘q",
            "Faqat Telegramda mumkin"
        ],
        "correct": 1,
        "info": "To‘g‘ri. Karta ma'lumotlarini hech kimga bermang."
    },
    {
        "q": "Telegramdan 'sovrin yutdingiz' degan shubhali xabar kelsa nima qilasiz?",
        "options": [
            "Havolani bosaman",
            "Shaxsiy ma'lumotlarni yuboraman",
            "Xabarni tekshiraman va shubhali bo‘lsa e'tibor bermayman"
        ],
        "correct": 2,
        "info": "To‘g‘ri. Firibgarlar ko‘pincha soxta sovrinlar orqali odamlarni aldashadi."
    }
]


async def send_public_home(message_or_call, ref_code: str | None = None):
    bot = message_or_call.bot
    bot_username = (await bot.me()).username

    # Referral linkdan kirgan foydalanuvchi menyuda yurib qolsa ham,
    # keyingi “Guruhga qo‘shish” tugmalarida aynan o‘sha ref_code saqlanadi.
    user_id = None
    if isinstance(message_or_call, types.CallbackQuery) and message_or_call.from_user:
        user_id = message_or_call.from_user.id
    elif getattr(message_or_call, "from_user", None):
        user_id = message_or_call.from_user.id
    if not ref_code and user_id:
        ref_code = await get_user_referral_click(user_id)

    text = (
        "👋 <b>Salom! Men guruh xavfsizligi uchun yordamchi botman.</b>\n\n"
        "Men guruhlarda shubhali fayllar, nomaqbul so‘zlar va firibgarlik urinishlarini kamaytirishga yordam beraman.\n\n"
        "🛡 <b>Nimalarga yordam beraman?</b>\n"
        "• shubhali fayllarni aniqlash;\n"
        "• ikki martalik fayl nomlarini sezish, masalan <code>photo.jpg.apk</code>;\n"
        "• nomaqbul so‘zlarni nazorat qilish;\n"
        "• guruh a’zolarini xavfsizlik bo‘yicha ogohlantirish;\n"
        "• foydalanuvchilarga qisqa qo‘llanma va testlar berish.\n\n"
        "Boshlash uchun quyidagi tugmalardan foydalaning 👇"
    )
    if ref_code:
        text += (
            "\n\n🔗 <b>Ssilka saqlandi.</b> Endi pastdagi <b>Guruhga qo‘shish</b> tugmasi orqali "
            "botni guruhingizga admin qilib qo‘shing. Xuddi shu ssilkani boshqalarga ham ulashsangiz, "
            "ular qo‘shgan guruhlar ham shu ssilka statistikasiga yoziladi."
        )
    if isinstance(message_or_call, types.CallbackQuery):
        await safe_edit_text(message_or_call.message, text, reply_markup=public_home_kb(bot_username, ref_code))
        await message_or_call.answer()
    else:
        await message_or_call.answer(text, reply_markup=public_home_kb(bot_username, ref_code))




async def _register_started_chat(message: types.Message, payload: str = ""):
    """Guruh/kanalda /start ref_xxx kelganda chatni saqlaydi va referralga bog‘laydi."""
    try:
        me = await message.bot.get_me()
        bot_member = await message.bot.get_chat_member(message.chat.id, me.id)
        is_bot_admin = 1 if bot_member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} else 0
        bot_status = getattr(bot_member.status, "value", str(bot_member.status))
    except Exception:
        is_bot_admin = 0
        bot_status = "unknown"

    await add_or_update_chat(
        message.chat.id,
        message.chat.title or "Noma’lum",
        message.chat.type,
        await get_chat_link(message.chat),
        is_bot_admin,
        bot_status,
    )

    if payload.startswith("ref_"):
        await track_referral_chat(payload, message.chat.id, message.from_user.id if message.from_user else None)


@router.message(Command("start", "panel", "help"))
async def start_handler(message: types.Message, command: CommandObject):
    await add_or_update_user(message.from_user)

    payload = (command.args or "").strip() if command else ""
    # CommandObject args bo‘sh bo‘lsa, textdan ham payloadni ajratib olamiz.
    if not payload and message.text:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) == 2 and parts[0].startswith("/start"):
            payload = parts[1].strip()

    if message.chat.type in {"group", "supergroup", "channel"}:
        await _register_started_chat(message, payload)

        await message.answer(
            "✅ <b>Bot guruhga muvaffaqiyatli qo‘shildi!</b>\n\n"
            "Botning barcha imkoniyatlaridan foydalanish uchun uni administrator qiling.\n\n"
            "Administrator qilingandan so‘ng bot:\n"
            "• Taqiqlangan xabarlarni o‘chiradi;\n"
            "• Qoidabuzar foydalanuvchilarga cheklov qo‘yadi;\n"
            "• Guruh xavfsizligini avtomatik nazorat qiladi."
        )
        return

    # Referral/giper ssilka private chatda saqlanadi.
    # Muhim: buni admin paneldan OLDIN tekshiramiz, chunki admin ham oddiy user kabi
    # referral linkni sinab ko‘rishi mumkin. Keyin shu user botni guruh/kanalga
    # qo‘shsa, my_chat_member event.from_user orqali chat shu ssilkaga bog‘lanadi.
    active_ref_code = None
    if payload.startswith("ref_"):
        saved = await save_user_referral_click(message.from_user.id, payload)
        if saved:
            active_ref_code = payload

    if await has_panel_access(message.from_user.id):
        if active_ref_code:
            await send_public_home(message, active_ref_code)
        else:
            await message.answer("👋 <b>Admin panel</b>\nKerakli bo‘limni tanlang:", reply_markup=await panel_menu_kb(message.from_user.id))
        return

    await send_public_home(message, active_ref_code)


@router.channel_post(F.text.startswith("/start"))
async def channel_start_handler(message: types.Message):
    # startchannel=ref_xxx bilan kanalga qo‘shilganda Telegram /start ref_xxx
    # postini yuborsa, shu yerda kanal referralga bog‘lanadi.
    payload = ""
    if message.text:
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) == 2:
            payload = parts[1].strip()
    await _register_started_chat(message, payload)


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
        reply_markup=guide_menu_kb(bot_username, await get_user_referral_click(call.from_user.id)),
    )
    await call.answer()


@router.callback_query(F.data.startswith("guide:"))
async def guide_detail(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    key = call.data.split(":", 1)[1]
    texts = {
        "add": (
            "1️⃣ <b>Botni guruhga qo‘shish</b>\n\n"
            "Pastdagi <b>Guruhga qo‘shish</b> tugmasini bosing va kerakli guruhni tanlang.\n\n"
            "Agar guruh ro‘yxatda chiqmasa, sizda o‘sha guruhga bot qo‘shish huquqi bo‘lmasligi mumkin."
        ),
        "rights": (
            "2️⃣ <b>Botni ishga tayyorlash</b>\n\n"
            "Bot guruhni yaxshi himoya qilishi uchun unga kerakli ruxsatlarni bering.\n\n"
            "Shundan so‘ng bot zararli fayllar, shubhali xabarlar va qoidabuzarliklarni aniqlashga yordam beradi."
        ),
        "panel": (
            "3️⃣ <b>Botdan foydalanish</b>\n\n"
            "Bot guruhdagi xavfsizlikni avtomatik kuzatadi.\n\n"
            "Foydalanuvchilar qo‘llanmani o‘qishi, xavfsizlik bo‘yicha maslahatlar olishi va test orqali bilimini tekshirishi mumkin."
        ),
        "files": (
            "4️⃣ <b>Xavfli fayllardan ehtiyot bo‘ling</b>\n\n"
            "<code>.apk</code>, <code>.exe</code>, <code>.bat</code>, <code>.js</code> kabi fayllar zararli bo‘lishi mumkin.\n\n"
            "Ayniqsa <code>photo.jpg.apk</code> kabi nomlangan fayllarga ehtiyot bo‘ling. Ular rasmga o‘xshab ko‘rinsa ham, aslida dastur bo‘lishi mumkin."
        ),
        "test": (
            "5️⃣ <b>Xavfsizlik bilimlarini tekshirish</b>\n\n"
            "Bot ichidagi qisqa test orqali shubhali fayllar, havolalar, parollar va firibgarlik holatlari bo‘yicha bilimingizni sinab ko‘rishingiz mumkin.\n\n"
            "Test oddiy va foydali savollardan iborat."
        ),
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
        "file": (
            "🦠 <b>Shubhali fayl misoli</b>\n\n"
            "Kimdir guruhga <code>game.apk</code> yoki <code>photo.jpg.apk</code> yuborsa, bu xavfli bo‘lishi mumkin.\n\n"
            "Bunday fayllarni ochishdan oldin manbasini tekshirish kerak."
        ),
        "word": (
            "🚫 <b>Nomaqbul so‘zlar nazorati</b>\n\n"
            "Guruhda haqorat, spam yoki nomaqbul so‘zlar ko‘payib ketsa, bot ularni kamaytirishga yordam beradi.\n\n"
            "Bu guruh muhitini toza va xavfsiz saqlashga xizmat qiladi."
        ),
        "warn": (
            "⚠️ <b>Ogohlantirish misoli</b>\n\n"
            "Agar foydalanuvchi qayta-qayta qoida buzsa, bot uni ogohlantiradi.\n\n"
            "Bu guruh a’zolariga qoidalarga rioya qilishni eslatadi."
        ),
    }
    await safe_edit_text(call.message, texts.get(key, "Demo topilmadi."), reply_markup=public_back_kb(bot_username, "pub:demo"))
    await call.answer()


@router.callback_query(F.data == "pub:features")
async def public_features(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    await safe_edit_text(
        call.message,
        "⚙️ <b>Bot imkoniyatlari</b>\n\n"
        "🛡 Shubhali fayllarni aniqlashga yordam beradi.\n"
        "🔗 Xavfli havolalardan ehtiyot bo‘lishni eslatadi.\n"
        "🚫 Nomaqbul so‘zlar va spamni kamaytirishga yordam beradi.\n"
        "📖 Foydalanuvchilar uchun qo‘llanma beradi.\n"
        "🧪 Xavfsizlik bo‘yicha qisqa test orqali bilimni tekshiradi.",
        reply_markup=public_back_kb(bot_username),
    )
    await call.answer()


@router.callback_query(F.data == "pub:support")
async def public_support(call: types.CallbackQuery):
    bot_username = (await call.bot.me()).username
    await safe_edit_text(
        call.message,
        "🆘 <b>Yordam</b>\n\n"
        "Agar bot guruhda ishlamayotgandek ko‘rinsa, quyidagilarni tekshiring:\n\n"
        "1. Bot guruhga qo‘shilganmi?\n"
        "2. Bot guruhda administrator qilinganmi?\n"
        "3. Botdan foydalanish uchun internet aloqasi barqarormi?\n"
        "4. Guruhda botga xabar yuborish imkoniyati bormi?\n\n"
        "Muammo davom etsa, bot egasi yoki guruh mas’uli bilan bog‘laning.",
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
                [InlineKeyboardButton(text="📢 Kanalga qo‘shish", url=add_channel_url(bot_username))],
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
