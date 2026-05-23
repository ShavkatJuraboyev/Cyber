# Cyber — kuchaytirilgan Telegram xavfsizlik boti

Bot guruhda:
- xavfli fayl kengaytmalarini bloklaydi;
- ikki martalik kengaytmali fayllarni aniqlaydi (`photo.jpg.exe`);
- arxivlarni bloklashni yoqib/o‘chiradi;
- yomon so‘zlarni o‘chiradi;
- ogohlantirish limitidan keyin foydalanuvchini vaqtincha mute qiladi;
- admin panel orqali sozlamalarni boshqaradi;
- oq ro‘yxat, loglar, foydalanuvchilar va eksport funksiyalarini beradi.

## O‘rnatish

```bash
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` ichiga token va admin ID larni yozing:

```env
BOT_TOKEN=TOKEN_BU_YERGA
ADMIN_IDS=123456789,987654321
DB_PATH=chat.db
```

Ishga tushirish:

```bash
python bot.py
```

## Muhim

Eski `config.py` ichida token ochiq yozilgan edi. BotFather orqali eski tokenni bekor qilib, yangi token oling.
