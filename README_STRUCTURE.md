# Cyber bot structured version

## Tuzilma

```text
Cyber_structured/
  bot.py
  config.py
  database.py
  handlers/
    common.py
    user.py
    admin.py
    superadmin.py
    group.py
  keyboards/
    admin_kb.py
    user_kb.py
  services/
    permissions.py
    admin_service.py
    security_service.py
  utils/
    file_export.py
```

## Maqsad

- `handlers/user.py` — `/start`, help, demo, FAQ, oddiy foydalanuvchi menyusi.
- `handlers/admin.py` — admin panel modullari: statistika, referral, sozlama, whitelist, broadcast, export, foydalanuvchilar.
- `handlers/superadmin.py` — superadmin: admin yaratish/o‘chirish, CRUD huquqlar, rollar, audit, vaqtinchalik admin, maxfiy log guruhi.
- `handlers/group.py` — guruhdagi xavfsizlik: yomon so‘z, xavfli fayl, `.apk/.exe`, double extension, log, delete/mute.
- `handlers/common.py` — umumiy state, permission helper, kichik util funksiyalar.
- `keyboards/` — keyboard helperlar uchun alohida import joyi.
- `services/` — permission/admin/security servislarini alohida ishlatish uchun import qatlam.
