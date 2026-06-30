import aiosqlite
import logging
from datetime import datetime, timedelta
import time
from utils.timezone import now_samarkand_str, now_samarkand
from config import DB_PATH

logger = logging.getLogger(__name__)


ARCHIVE_EXTENSIONS = [".zip", ".rar", ".7z", ".tar", ".gz"]

# Tezkor guruh tekshiruvlari uchun kichik TTL cache.
# 1000+ foydalanuvchi yozganda har xabar uchun 3-4 marta SQLite ochilishini kamaytiradi.
_CACHE_TTL = 30
_settings_cache: dict[int, tuple[float, dict]] = {}
_bad_words_cache: dict[int | None, tuple[float, list[str]]] = {}
_unsafe_ext_cache: dict[int | None, tuple[float, list[str]]] = {}
_whitelist_cache: dict[tuple[int, int], tuple[float, bool]] = {}

def _cache_get(cache: dict, key):
    item = cache.get(key)
    if not item:
        return None
    ts, value = item
    if time.monotonic() - ts > _CACHE_TTL:
        cache.pop(key, None)
        return None
    return value

def _cache_set(cache: dict, key, value):
    cache[key] = (time.monotonic(), value)
    return value

def clear_runtime_cache():
    _settings_cache.clear()
    _bad_words_cache.clear()
    _unsafe_ext_cache.clear()
    _whitelist_cache.clear()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            type TEXT,
            invite_link TEXT,
            is_bot_admin INTEGER DEFAULT 0,
            bot_status TEXT DEFAULT 'unknown',
            member_count INTEGER DEFAULT NULL,
            member_count_updated_at TIMESTAMP,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # eski bazalarda invite_link bo‘lmasa qo‘shadi
        cursor = await db.execute("PRAGMA table_info(chats)")
        columns = await cursor.fetchall()

        column_names = [column[1] for column in columns]

        if "invite_link" not in column_names:
            await db.execute(
                "ALTER TABLE chats ADD COLUMN invite_link TEXT"
            )

        if "bot_status" not in column_names:
            await db.execute(
                "ALTER TABLE chats ADD COLUMN bot_status TEXT DEFAULT 'unknown'"
            )

        if "updated_at" not in column_names:
            await db.execute(
                "ALTER TABLE chats ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )

        if "member_count" not in column_names:
            await db.execute(
                "ALTER TABLE chats ADD COLUMN member_count INTEGER DEFAULT NULL"
            )

        if "member_count_updated_at" not in column_names:
            await db.execute(
                "ALTER TABLE chats ADD COLUMN member_count_updated_at TIMESTAMP"
            )

        # Eski bazada member_count ustuni yangi qo‘shilganda hamma chatlarga 0 yozilgan bo‘lishi mumkin.
        # 0 real a'zolar soni emas, "hali olinmagan" degani. Shuning uchun NULL qilib qo‘yamiz.
        await db.execute("""
            UPDATE chats
            SET member_count=NULL
            WHERE member_count=0 AND member_count_updated_at IS NULL
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            language_code TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS bad_words (
            chat_id INTEGER,
            word TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, word)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER PRIMARY KEY,
            mute_minutes INTEGER DEFAULT 10,
            max_warnings INTEGER DEFAULT 3,
            max_file_mb INTEGER DEFAULT 20,
            delete_service_messages INTEGER DEFAULT 0,
            block_archives INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Eski bazalarda settings jadvalida yangi ustunlar bo'lmasligi mumkin.
        cursor = await db.execute("PRAGMA table_info(settings)")
        settings_columns = [column[1] for column in await cursor.fetchall()]
        if "max_file_mb" not in settings_columns:
            await db.execute("ALTER TABLE settings ADD COLUMN max_file_mb INTEGER DEFAULT 20")
        if "delete_service_messages" not in settings_columns:
            await db.execute("ALTER TABLE settings ADD COLUMN delete_service_messages INTEGER DEFAULT 0")
        if "block_archives" not in settings_columns:
            await db.execute("ALTER TABLE settings ADD COLUMN block_archives INTEGER DEFAULT 0")
        if "updated_at" not in settings_columns:
            await db.execute("ALTER TABLE settings ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            chat_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS unsafe_extensions (
            chat_id INTEGER,
            ext TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, ext)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            chat_id INTEGER,
            user_id INTEGER,
            count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(chat_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            action TEXT NOT NULL,
            reason TEXT,
            file_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS referral_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS referral_link_chats (
            link_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(link_id, chat_id),
            FOREIGN KEY(link_id) REFERENCES referral_links(id) ON DELETE CASCADE,
            FOREIGN KEY(chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
        )
        """)

        cursor = await db.execute("PRAGMA table_info(referral_link_chats)")
        referral_chat_columns = [column[1] for column in await cursor.fetchall()]
        if "added_by" not in referral_chat_columns:
            await db.execute("ALTER TABLE referral_link_chats ADD COLUMN added_by INTEGER")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS user_referral_clicks (
            user_id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS panel_admins (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Panel admin uchun muddatli ruxsat muddati (eski bazaga ham qo'shiladi)
        cursor = await db.execute("PRAGMA table_info(panel_admins)")
        panel_admin_columns = [column[1] for column in await cursor.fetchall()]
        if "expires_at" not in panel_admin_columns:
            await db.execute("ALTER TABLE panel_admins ADD COLUMN expires_at TIMESTAMP")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER,
            target_user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_private_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS private_log_chats (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            type TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Eski versiyadagi bitta maxfiy guruh sozlamasini yangi ko‘p-guruh jadvaliga ko‘chirish.
        cur = await db.execute("SELECT value FROM bot_private_settings WHERE key='private_log_chat_id'")
        old_secret = await cur.fetchone()
        if old_secret and old_secret[0]:
            try:
                old_chat_id = int(old_secret[0])
                await db.execute("""
                    INSERT OR IGNORE INTO private_log_chats (chat_id, title, type)
                    VALUES (?, 'Maxfiy guruh', 'supergroup')
                """, (old_chat_id,))
            except (TypeError, ValueError):
                pass

        await db.execute("""
        CREATE TABLE IF NOT EXISTS panel_admin_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            allowed INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, permission),
            FOREIGN KEY(user_id) REFERENCES panel_admins(user_id) ON DELETE CASCADE
        )
        """)



        await db.execute("""
        CREATE TABLE IF NOT EXISTS stats_cache (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            chats_count INTEGER DEFAULT 0,
            member_chats INTEGER DEFAULT 0,
            bot_admin_chats INTEGER DEFAULT 0,
            not_member_chats INTEGER DEFAULT 0,
            groups_count INTEGER DEFAULT 0,
            channels_count INTEGER DEFAULT 0,
            group_member_chats INTEGER DEFAULT 0,
            channel_member_chats INTEGER DEFAULT 0,
            group_admin_chats INTEGER DEFAULT 0,
            channel_admin_chats INTEGER DEFAULT 0,
            users_count INTEGER DEFAULT 0,
            unsafe_ext_count INTEGER DEFAULT 0,
            bad_words_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS referral_stats_cache (
            link_id INTEGER PRIMARY KEY,
            groups_count INTEGER DEFAULT 0,
            admin_count INTEGER DEFAULT 0,
            member_count INTEGER DEFAULT 0,
            not_member_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(link_id) REFERENCES referral_links(id) ON DELETE CASCADE
        )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chats_status ON chats(bot_status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chats_type_admin ON chats(type, is_bot_admin)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referral_link_chats_link_added ON referral_link_chats(link_id, added_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referral_link_chats_chat ON referral_link_chats(chat_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_referral_link_chats_link_id ON referral_link_chats(link_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chats_admin_status ON chats(is_bot_admin, bot_status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chats_member_count ON chats(member_count)")

        # CRUD/ROLE tizimi. Eski baza o'chmaydi, yangi jadvallar qo'shiladi.
        await db.execute("""
        CREATE TABLE IF NOT EXISTS panel_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS panel_role_permissions (
            role_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            allowed INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(role_id, permission),
            FOREIGN KEY(role_id) REFERENCES panel_roles(id) ON DELETE CASCADE
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS panel_admin_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            assigned_by INTEGER,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, role_id),
            FOREIGN KEY(user_id) REFERENCES panel_admins(user_id) ON DELETE CASCADE,
            FOREIGN KEY(role_id) REFERENCES panel_roles(id) ON DELETE CASCADE
        )
        """)

        # Katta bazalarda panel va xavfsizlik tekshiruvlari qotmasligi uchun indekslar.
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_updated_at ON users(updated_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_security_logs_id ON security_logs(id DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bad_words_chat_word ON bad_words(chat_id, word)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_unsafe_extensions_chat_ext ON unsafe_extensions(chat_id, ext)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_whitelist_chat_user ON whitelist(chat_id, user_id)")

        await db.commit()


async def add_or_update_chat(
    chat_id: int,
    title: str,
    chat_type: str,
    invite_link: str | None = None,
    is_admin: int | None = None,
    bot_status: str | None = None,
):
    """
    Chat ma'lumotini saqlaydi.

    Muhim: is_admin=None bo'lsa bazadagi admin status o'zgarmaydi.
    Bu umumiy message handler har bir xabarda admin statusni 0 qilib yubormasligi uchun kerak.
    """
    title = title or "Noma’lum"
    async with aiosqlite.connect(DB_PATH) as db:
        if is_admin is None:
            await db.execute("""
            INSERT INTO chats (chat_id, title, type, invite_link, bot_status)
            VALUES (?, ?, ?, ?, COALESCE(?, 'unknown'))
            ON CONFLICT(chat_id) DO UPDATE SET
                title=excluded.title,
                type=excluded.type,
                invite_link=COALESCE(excluded.invite_link, chats.invite_link),
                bot_status=COALESCE(?, chats.bot_status),
                updated_at=CURRENT_TIMESTAMP
            """, (chat_id, title, chat_type, invite_link, bot_status, bot_status))
        else:
            is_admin = 1 if int(is_admin) == 1 else 0
            bot_status = bot_status or ("administrator" if is_admin else "member")
            await db.execute("""
            INSERT INTO chats (chat_id, title, type, invite_link, is_bot_admin, bot_status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title=excluded.title,
                type=excluded.type,
                invite_link=COALESCE(excluded.invite_link, chats.invite_link),
                is_bot_admin=excluded.is_bot_admin,
                bot_status=excluded.bot_status,
                updated_at=CURRENT_TIMESTAMP
            """, (chat_id, title, chat_type, invite_link, is_admin, bot_status))
        await db.commit()


async def update_chat_bot_status(chat_id: int, is_admin: int, bot_status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE chats
            SET is_bot_admin=?, bot_status=?, updated_at=CURRENT_TIMESTAMP
            WHERE chat_id=?
        """, (1 if is_admin else 0, bot_status, chat_id))
        await db.commit()

async def get_stats_summary():
    async with aiosqlite.connect(DB_PATH) as db:
        async def fetch_count(sql: str, params: tuple = ()) -> int:
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return int(row[0] or 0)

        inactive_statuses = ("not_member", "left", "kicked")
        inactive_sql = "COALESCE(bot_status, 'unknown') IN ('not_member', 'left', 'kicked')"
        active_sql = f"NOT ({inactive_sql})"

        chats_count = await fetch_count("SELECT COUNT(*) FROM chats")
        bot_admin_chats = await fetch_count("SELECT COUNT(*) FROM chats WHERE is_bot_admin=1")
        not_member_chats = await fetch_count(f"SELECT COUNT(*) FROM chats WHERE {inactive_sql}")
        member_chats = await fetch_count(f"SELECT COUNT(*) FROM chats WHERE {active_sql}")

        groups_count = await fetch_count("SELECT COUNT(*) FROM chats WHERE type IN ('group', 'supergroup')")
        channels_count = await fetch_count("SELECT COUNT(*) FROM chats WHERE type='channel'")
        group_member_chats = await fetch_count(f"SELECT COUNT(*) FROM chats WHERE type IN ('group', 'supergroup') AND {active_sql}")
        channel_member_chats = await fetch_count(f"SELECT COUNT(*) FROM chats WHERE type='channel' AND {active_sql}")
        group_admin_chats = await fetch_count("SELECT COUNT(*) FROM chats WHERE type IN ('group', 'supergroup') AND is_bot_admin=1")
        channel_admin_chats = await fetch_count("SELECT COUNT(*) FROM chats WHERE type='channel' AND is_bot_admin=1")

        users_count = await fetch_count("SELECT COUNT(*) FROM users")
        unsafe_ext_count = await fetch_count("SELECT COUNT(*) FROM unsafe_extensions WHERE chat_id IS NULL")
        bad_words_count = await fetch_count("SELECT COUNT(*) FROM bad_words WHERE chat_id IS NULL")

        return {
            "chats_count": chats_count,
            "member_chats": member_chats,
            "bot_admin_chats": bot_admin_chats,
            "not_member_chats": not_member_chats,
            "groups_count": groups_count,
            "channels_count": channels_count,
            "group_member_chats": group_member_chats,
            "channel_member_chats": channel_member_chats,
            "group_admin_chats": group_admin_chats,
            "channel_admin_chats": channel_admin_chats,
            "users_count": users_count,
            "unsafe_ext_count": unsafe_ext_count,
            "bad_words_count": bad_words_count,
        }


async def delete_chat(chat_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("DELETE FROM referral_link_chats WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM bad_words WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM settings WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM whitelist WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM unsafe_extensions WHERE chat_id=?", (chat_id,))
        await db.execute("DELETE FROM warnings WHERE chat_id=?", (chat_id,))
        cur = await db.execute("DELETE FROM chats WHERE chat_id=?", (chat_id,))
        await db.commit()
        return cur.rowcount > 0


async def get_all_chats(limit: int | None = None, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        sql = """
            SELECT chat_id, title, type, invite_link, is_bot_admin, COALESCE(bot_status, 'unknown')
            FROM chats
            ORDER BY updated_at DESC
        """
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (int(limit), int(offset))
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()


async def get_chat_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM chats")
        return (await cursor.fetchone())[0]


async def add_or_update_user(user):
    if not user:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO users (user_id, first_name, last_name, username, language_code)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            username=excluded.username,
            language_code=excluded.language_code,
            updated_at=CURRENT_TIMESTAMP
        """, (
            user.id,
            user.first_name or "",
            user.last_name or "",
            user.username or "",
            getattr(user, "language_code", None)
        ))
        await db.commit()


async def get_all_users(limit: int | None = None, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        sql = """
            SELECT user_id, first_name, last_name, username, language_code, joined_at
            FROM users
            ORDER BY updated_at DESC
        """
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (int(limit), int(offset))
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()


async def get_user_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        return (await cursor.fetchone())[0]


async def get_user_by_id(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, first_name, last_name, username, language_code, joined_at
            FROM users WHERE user_id=?
        """, (user_id,))
        return await cursor.fetchone()


async def add_bad_word(word: str, chat_id: int | None = None) -> bool:
    word = (word or "").strip().lower()
    if not word:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO bad_words (chat_id, word) VALUES (?, ?)",
            (chat_id, word)
        )
        await db.commit()
        clear_runtime_cache()
        return cur.rowcount > 0


async def remove_bad_word(word: str, chat_id: int | None = None) -> bool:
    word = (word or "").strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            cur = await db.execute("DELETE FROM bad_words WHERE word=? AND chat_id IS NULL", (word,))
        else:
            cur = await db.execute("DELETE FROM bad_words WHERE word=? AND chat_id=?", (word, chat_id))
        await db.commit()
        clear_runtime_cache()
        return cur.rowcount > 0


async def list_bad_words(chat_id: int | None = None):
    cached = _cache_get(_bad_words_cache, chat_id)
    if cached is not None:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            cursor = await db.execute("SELECT word FROM bad_words WHERE chat_id IS NULL ORDER BY word")
        else:
            cursor = await db.execute("""
                SELECT word FROM bad_words
                WHERE chat_id IS NULL OR chat_id=?
                GROUP BY word
                ORDER BY word
            """, (chat_id,))
        rows = await cursor.fetchall()
        return _cache_set(_bad_words_cache, chat_id, [r[0] for r in rows])


async def _settings_row_to_dict(row):
    return {
        "mute_minutes": row[0],
        "max_warnings": row[1],
        "max_file_mb": row[2],
        "delete_service_messages": bool(row[3]),
        "block_archives": bool(row[4]),
    }


async def get_global_settings():
    """chat_id=0 umumiy sozlamalar sifatida ishlatiladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO settings (chat_id) VALUES (0)")
        await db.commit()
        cursor = await db.execute("""
            SELECT mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives
            FROM settings WHERE chat_id=0
        """)
        row = await cursor.fetchone()
        return _cache_set(_settings_cache, 0, await _settings_row_to_dict(row))


async def get_settings(chat_id: int):
    cached = _cache_get(_settings_cache, chat_id)
    if cached is not None:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        # Yangi guruhlar uchun default qiymatlar umumiy sozlamadan olinadi.
        await db.execute("INSERT OR IGNORE INTO settings (chat_id) VALUES (0)")
        await db.execute("""
            INSERT OR IGNORE INTO settings (chat_id, mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives)
            SELECT ?, mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives
            FROM settings WHERE chat_id=0
        """, (chat_id,))
        await db.commit()
        cursor = await db.execute("""
            SELECT mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives
            FROM settings WHERE chat_id=?
        """, (chat_id,))
        row = await cursor.fetchone()
        return await _settings_row_to_dict(row)


async def get_mute_minutes(chat_id: int | None) -> int:
    if chat_id is None:
        return 10
    return (await get_settings(chat_id))["mute_minutes"]


async def set_mute_minutes(chat_id: int, minutes: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO settings (chat_id, mute_minutes)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                mute_minutes=excluded.mute_minutes,
                updated_at=CURRENT_TIMESTAMP
        """, (chat_id, minutes))
        await db.commit()
        clear_runtime_cache()
        return True


async def update_setting(chat_id: int, key: str, value: int):
    allowed = {"mute_minutes", "max_warnings", "max_file_mb", "delete_service_messages", "block_archives"}
    if key not in allowed:
        raise ValueError("Noto‘g‘ri sozlama nomi")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO settings (chat_id) VALUES (?)", (chat_id,))
        await db.execute(f"UPDATE settings SET {key}=?, updated_at=CURRENT_TIMESTAMP WHERE chat_id=?", (value, chat_id))
        await db.commit()
        clear_runtime_cache()


async def update_setting_for_all_chats(key: str, value: int) -> int:
    """Umumiy defaultni va bazadagi barcha guruh/kanal sozlamalarini yangilaydi."""
    allowed = {"mute_minutes", "max_warnings", "max_file_mb", "delete_service_messages", "block_archives"}
    if key not in allowed:
        raise ValueError("Noto‘g‘ri sozlama nomi")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO settings (chat_id) VALUES (0)")
        cursor = await db.execute("SELECT chat_id FROM chats")
        chat_ids = [row[0] for row in await cursor.fetchall()]

        for cid in chat_ids:
            await db.execute("""
                INSERT OR IGNORE INTO settings (chat_id, mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives)
                SELECT ?, mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives
                FROM settings WHERE chat_id=0
            """, (cid,))

        await db.execute(f"UPDATE settings SET {key}=?, updated_at=CURRENT_TIMESTAMP WHERE chat_id=0", (value,))
        if chat_ids:
            placeholders = ",".join("?" for _ in chat_ids)
            await db.execute(
                f"UPDATE settings SET {key}=?, updated_at=CURRENT_TIMESTAMP WHERE chat_id IN ({placeholders})",
                (value, *chat_ids),
            )
        await db.commit()
        clear_runtime_cache()
        return len(chat_ids)


async def add_whitelist_user(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO whitelist (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        await db.commit()
        clear_runtime_cache()


async def remove_whitelist_user(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await db.commit()
        clear_runtime_cache()


async def list_whitelist(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM whitelist WHERE chat_id=? ORDER BY created_at DESC", (chat_id,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    key = (chat_id, user_id)
    cached = _cache_get(_whitelist_cache, key)
    if cached is not None:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        return _cache_set(_whitelist_cache, key, await cursor.fetchone() is not None)


async def list_unsafe_extensions(chat_id: int | None = None):
    cached = _cache_get(_unsafe_ext_cache, chat_id)
    if cached is not None:
        return cached
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            cursor = await db.execute("SELECT ext FROM unsafe_extensions WHERE chat_id IS NULL ORDER BY ext")
        else:
            cursor = await db.execute("""
                SELECT ext FROM unsafe_extensions
                WHERE chat_id IS NULL OR chat_id=?
                GROUP BY ext ORDER BY ext
            """, (chat_id,))
        rows = await cursor.fetchall()
        return _cache_set(_unsafe_ext_cache, chat_id, [r[0] for r in rows])


async def add_unsafe_extension(ext: str, chat_id: int | None = None):
    ext = (ext or "").strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO unsafe_extensions (chat_id, ext) VALUES (?, ?)", (chat_id, ext))
        await db.commit()
        clear_runtime_cache()


async def remove_unsafe_extension(ext: str, chat_id: int | None = None):
    ext = (ext or "").strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            await db.execute("DELETE FROM unsafe_extensions WHERE chat_id IS NULL AND ext=?", (ext,))
        else:
            await db.execute("DELETE FROM unsafe_extensions WHERE chat_id=? AND ext=?", (chat_id, ext))
        await db.commit()
        clear_runtime_cache()

async def remove_unsafe_all_extensions(chat_id: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            await db.execute("DELETE FROM unsafe_extensions WHERE chat_id IS NULL")
        else:
            await db.execute("DELETE FROM unsafe_extensions WHERE chat_id=?", (chat_id,))
        await db.commit()


async def add_warning(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO warnings (chat_id, user_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                count=count+1,
                updated_at=CURRENT_TIMESTAMP
        """, (chat_id, user_id))
        await db.commit()
        cursor = await db.execute("SELECT count FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        return (await cursor.fetchone())[0]


async def reset_warning(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM warnings WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await db.commit()


async def add_security_log(chat_id: int | None, user_id: int | None, action: str, reason: str = "", file_name: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO security_logs (chat_id, user_id, action, reason, file_name)
            VALUES (?, ?, ?, ?, ?)
        """, (chat_id, user_id, action, reason, file_name))
        await db.commit()


async def get_security_logs(limit: int = 20, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT chat_id, user_id, action, reason, file_name, created_at
            FROM security_logs
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (int(limit), int(offset)))
        return await cursor.fetchall()


async def get_security_log_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM security_logs")
        return (await cursor.fetchone())[0]


async def create_referral_link(name: str, code: str, created_by: int | None = None) -> int:
    name = (name or "").strip() or "Nomsiz havola"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO referral_links (name, code, created_by) VALUES (?, ?, ?)",
            (name, code, created_by)
        )
        await db.commit()
        return cursor.lastrowid


async def get_referral_link_by_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, name, code, created_by, created_at FROM referral_links WHERE code=?",
            (code,)
        )
        return await cursor.fetchone()


async def get_referral_link_by_id(link_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, name, code, created_by, created_at FROM referral_links WHERE id=?",
            (link_id,)
        )
        return await cursor.fetchone()


async def update_referral_link_name(link_id: int, name: str) -> bool:
    name = (name or "").strip()[:100] or "Nomsiz havola"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE referral_links SET name=? WHERE id=?",
            (name, link_id)
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_referral_link(link_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        # SQLite har bir connection uchun foreign_keys alohida yoqiladi.
        # Shuning uchun eski bazalarda ham bog‘langan chatlarni qo‘lda tozalaymiz.
        await db.execute("DELETE FROM referral_link_chats WHERE link_id=?", (link_id,))
        cursor = await db.execute("DELETE FROM referral_links WHERE id=?", (link_id,))
        await db.commit()
        return cursor.rowcount > 0


async def save_user_referral_click(user_id: int, code: str) -> bool:
    code = (code or "").strip()
    if not user_id or not code:
        return False
    link = await get_referral_link_by_code(code)
    if not link:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_referral_clicks (user_id, code, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                code=excluded.code,
                updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, code)
        )
        await db.commit()
        return True


async def get_user_referral_click(user_id: int, max_age_hours: int = 72) -> str | None:
    if not user_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT code
            FROM user_referral_clicks
            WHERE user_id=?
              AND datetime(updated_at) >= datetime('now', ?)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id, f"-{int(max_age_hours)} hours")
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def track_referral_chat_by_user(user_id: int, chat_id: int) -> bool:
    code = await get_user_referral_click(user_id)
    if not code:
        return False
    return await track_referral_chat(code, chat_id, user_id)


async def track_referral_chat(code: str, chat_id: int, added_by: int | None = None) -> bool:
    code = (code or "").strip()
    link = await get_referral_link_by_code(code)
    if not link:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO referral_link_chats (link_id, chat_id, added_by)
            VALUES (?, ?, ?)
            ON CONFLICT(link_id, chat_id) DO UPDATE SET
                added_by=COALESCE(referral_link_chats.added_by, excluded.added_by)
            """,
            (link[0], chat_id, added_by)
        )
        await db.commit()
        return True


async def get_referral_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                rl.id,
                rl.name,
                rl.code,
                COALESCE(rsc.admin_count, SUM(CASE WHEN c.is_bot_admin=1 THEN 1 ELSE 0 END), 0) AS groups_count,
                COALESCE(rsc.admin_count, SUM(CASE WHEN c.is_bot_admin=1 THEN 1 ELSE 0 END), 0) AS admin_count,
                rl.created_at,
                rsc.updated_at,
                COALESCE(rsc.member_count, SUM(CASE WHEN COALESCE(c.bot_status, 'unknown') NOT IN ('not_member','left','kicked') THEN 1 ELSE 0 END), 0) AS member_count,
                COALESCE(rsc.not_member_count, SUM(CASE WHEN COALESCE(c.bot_status, 'unknown') IN ('not_member','left','kicked') THEN 1 ELSE 0 END), 0) AS not_member_count
            FROM referral_links rl
            LEFT JOIN referral_stats_cache rsc ON rsc.link_id = rl.id
            LEFT JOIN referral_link_chats rlc ON rlc.link_id = rl.id AND rsc.link_id IS NULL
            LEFT JOIN chats c ON c.chat_id = rlc.chat_id AND rsc.link_id IS NULL
            GROUP BY rl.id
            ORDER BY rl.id DESC
        """)
        return await cursor.fetchall()


async def get_referral_chats(link_id: int, limit: int | None = None, offset: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        sql = """
            SELECT
                c.chat_id,
                c.title,
                c.type,
                c.is_bot_admin,
                COALESCE(c.bot_status, 'unknown'),
                rlc.added_at,
                rlc.added_by,
                c.member_count
            FROM referral_link_chats rlc
            JOIN chats c ON c.chat_id = rlc.chat_id
            WHERE rlc.link_id=? AND c.is_bot_admin=1
            ORDER BY rlc.added_at DESC
        """
        params: tuple = (link_id,)
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (link_id, int(limit), int(offset))
        cursor = await db.execute(sql, params)
        return await cursor.fetchall()


async def count_referral_chats_member_gt_10(link_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM referral_link_chats rlc
            JOIN chats c ON c.chat_id = rlc.chat_id
            WHERE rlc.link_id=?
              AND c.is_bot_admin=1
              AND c.member_count > 10
        """, (link_id,))
        row = await cursor.fetchone()
        return int(row[0] or 0)


async def update_chat_member_count(chat_id: int, member_count: int | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE chats
            SET member_count=?,
                member_count_updated_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE chat_id=?
        """, (None if member_count is None else int(member_count), chat_id))
        await db.commit()

async def get_chats_without_referral():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT c.chat_id, c.title, c.type, c.invite_link, c.is_bot_admin, COALESCE(c.bot_status, 'unknown')
            FROM chats c
            LEFT JOIN referral_link_chats rlc ON rlc.chat_id = c.chat_id
            WHERE rlc.chat_id IS NULL
            ORDER BY c.updated_at DESC
        """)
        return await cursor.fetchall()


async def assign_chat_to_referral(link_id: int, chat_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM referral_links WHERE id=?", (link_id,))
        if not await cur.fetchone():
            return False
        cur = await db.execute("SELECT 1 FROM chats WHERE chat_id=?", (chat_id,))
        if not await cur.fetchone():
            return False
        await db.execute(
            "INSERT OR IGNORE INTO referral_link_chats (link_id, chat_id) VALUES (?, ?)",
            (link_id, chat_id)
        )
        await db.commit()
        return True


# ---------------- PANEL ADMINLAR VA HUQUQLAR ----------------

async def add_panel_admin(user_id: int, full_name: str = "", username: str = "", created_by: int | None = None, expires_days: int | None = None):
    expires_at = None
    if expires_days and int(expires_days) > 0:
        expires_at = (now_samarkand() + timedelta(days=int(expires_days))).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO panel_admins (user_id, full_name, username, is_active, created_by, expires_at)
        VALUES (?, ?, ?, 1, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name=excluded.full_name,
            username=excluded.username,
            is_active=1,
            expires_at=excluded.expires_at,
            updated_at=CURRENT_TIMESTAMP
        """, (user_id, full_name or "", username or "", created_by, expires_at))
        await db.commit()


async def remove_panel_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM panel_admin_permissions WHERE user_id=?", (user_id,))
        cur = await db.execute("DELETE FROM panel_admins WHERE user_id=?", (user_id,))
        await db.commit()
        return cur.rowcount > 0


async def list_panel_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, full_name, username, is_active, created_by, created_at, expires_at
            FROM panel_admins
            ORDER BY created_at DESC
        """)
        return await cursor.fetchall()


async def get_panel_admin(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, full_name, username, is_active, created_by, created_at, expires_at
            FROM panel_admins
            WHERE user_id=?
        """, (user_id,))
        return await cursor.fetchone()


async def set_panel_admin_permission(user_id: int, permission: str, allowed: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO panel_admin_permissions (user_id, permission, allowed)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, permission) DO UPDATE SET
            allowed=excluded.allowed,
            updated_at=CURRENT_TIMESTAMP
        """, (user_id, permission, 1 if allowed else 0))
        await db.commit()


async def get_panel_admin_permissions(user_id: int) -> set[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT permission
            FROM panel_admin_permissions
            WHERE user_id=? AND allowed=1
        """, (user_id,))
        return {row[0] for row in await cursor.fetchall()}


async def panel_admin_has_permission(user_id: int, permission: str) -> bool:
    admin = await get_panel_admin(user_id)
    if not admin or int(admin[3]) != 1:
        return False
    perms = await get_panel_admin_permissions(user_id)
    return permission in perms


# ---------------- CRUD ROLE PERMISSIONS ----------------

async def create_panel_role(name: str, description: str = "", created_by: int | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        role_name = name.strip()
        await db.execute("""
            INSERT INTO panel_roles (name, description, created_by)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description=excluded.description,
                updated_at=CURRENT_TIMESTAMP
        """, (role_name, description or "", created_by))
        cur = await db.execute("SELECT id FROM panel_roles WHERE name=?", (role_name,))
        row = await cur.fetchone()
        await db.commit()
        return int(row[0])


async def update_panel_role(role_id: int, name: str, description: str = "") -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            UPDATE panel_roles
            SET name=?, description=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (name.strip(), description or "", role_id))
        await db.commit()
        return cur.rowcount > 0


async def delete_panel_role(role_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM panel_roles WHERE id=?", (role_id,))
        await db.commit()
        return cur.rowcount > 0


async def list_panel_roles():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id, name, COALESCE(description, ''), created_by, created_at
            FROM panel_roles
            ORDER BY id DESC
        """)
        return await cur.fetchall()


async def get_panel_role(role_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id, name, COALESCE(description, ''), created_by, created_at
            FROM panel_roles
            WHERE id=?
        """, (role_id,))
        return await cur.fetchone()


async def set_panel_role_permission(role_id: int, permission: str, allowed: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO panel_role_permissions (role_id, permission, allowed)
            VALUES (?, ?, ?)
            ON CONFLICT(role_id, permission) DO UPDATE SET
                allowed=excluded.allowed,
                updated_at=CURRENT_TIMESTAMP
        """, (role_id, permission, 1 if allowed else 0))
        await db.commit()


async def get_panel_role_permissions(role_id: int) -> set[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT permission
            FROM panel_role_permissions
            WHERE role_id=? AND allowed=1
        """, (role_id,))
        return {row[0] for row in await cur.fetchall()}


async def assign_role_to_admin(user_id: int, role_id: int, assigned_by: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO panel_admin_roles (user_id, role_id, assigned_by)
            VALUES (?, ?, ?)
        """, (user_id, role_id, assigned_by))
        await db.commit()


async def remove_role_from_admin(user_id: int, role_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM panel_admin_roles WHERE user_id=? AND role_id=?", (user_id, role_id))
        await db.commit()
        return cur.rowcount > 0


async def get_admin_roles(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT r.id, r.name, COALESCE(r.description, '')
            FROM panel_roles r
            JOIN panel_admin_roles ar ON ar.role_id=r.id
            WHERE ar.user_id=?
            ORDER BY r.name
        """, (user_id,))
        return await cur.fetchall()


async def get_admin_effective_permissions(user_id: int) -> set[str]:
    """Adminning o'ziga berilgan eski huquqlari + role orqali berilgan CRUD huquqlari."""
    perms = await get_panel_admin_permissions(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT rp.permission
            FROM panel_role_permissions rp
            JOIN panel_admin_roles ar ON ar.role_id=rp.role_id
            WHERE ar.user_id=? AND rp.allowed=1
        """, (user_id,))
        perms.update(row[0] for row in await cur.fetchall())
    return perms


async def panel_admin_has_effective_permission(user_id: int, permission: str) -> bool:
    admin = await get_panel_admin(user_id)
    if not admin or int(admin[3]) != 1:
        return False
    perms = await get_admin_effective_permissions(user_id)
    if permission in perms:
        return True
    # Masalan chats.delete bo'lsa, chats.* ham ruxsat hisoblanadi.
    module = permission.split('.', 1)[0]
    return f"{module}.*" in perms


async def set_panel_admin_expiry(user_id: int, expires_days: int | None):
    expires_at = None
    if expires_days and int(expires_days) > 0:
        expires_at = (now_samarkand() + timedelta(days=int(expires_days))).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE panel_admins SET expires_at=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (expires_at, user_id))
        await db.commit()


async def disable_expired_panel_admins() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            UPDATE panel_admins
            SET is_active=0, updated_at=CURRENT_TIMESTAMP
            WHERE is_active=1 AND expires_at IS NOT NULL AND datetime(expires_at) <= datetime(?)
        """, (now_samarkand_str(),))
        await db.commit()
        return cur.rowcount


async def add_admin_audit_log(actor_id: int | None, target_user_id: int | None, action: str, details: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO admin_audit_logs (actor_id, target_user_id, action, details)
            VALUES (?, ?, ?, ?)
        """, (actor_id, target_user_id, action, details or ""))
        await db.commit()


async def get_admin_audit_logs(limit: int = 30):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT actor_id, target_user_id, action, details, created_at
            FROM admin_audit_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return await cur.fetchall()


async def set_private_log_chat_id(chat_id: int | None):
    """Orqaga moslik uchun: None bo‘lsa hamma maxfiy guruhlarni tozalaydi, ID bo‘lsa bitta guruh qo‘shadi."""
    if chat_id is None:
        await clear_private_log_chats()
    else:
        await add_private_log_chat(chat_id, "Maxfiy guruh", "supergroup", None)


async def add_private_log_chat(chat_id: int, title: str | None = None, chat_type: str | None = None, added_by: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO private_log_chats (chat_id, title, type, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                title=excluded.title,
                type=excluded.type,
                added_by=COALESCE(excluded.added_by, private_log_chats.added_by),
                updated_at=CURRENT_TIMESTAMP
        """, (chat_id, title or "Maxfiy guruh", chat_type or "supergroup", added_by))
        await db.execute("""
            INSERT INTO bot_private_settings (key, value)
            VALUES ('private_log_chat_id', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """, (str(chat_id),))
        await db.commit()


async def remove_private_log_chat(chat_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM private_log_chats WHERE chat_id=?", (chat_id,))
        await db.commit()
        return cur.rowcount > 0


async def clear_private_log_chats():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM private_log_chats")
        await db.execute("DELETE FROM bot_private_settings WHERE key='private_log_chat_id'")
        await db.commit()


async def list_private_log_chats():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT chat_id, title, type, added_by, added_at
            FROM private_log_chats
            ORDER BY updated_at DESC
        """)
        return await cur.fetchall()


async def get_private_log_chat_id() -> int | None:
    rows = await list_private_log_chats()
    if rows:
        return int(rows[0][0])
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM bot_private_settings WHERE key='private_log_chat_id'")
        row = await cur.fetchone()
        if not row or not row[0]:
            return None
        try:
            return int(row[0])
        except ValueError:
            return None


async def get_private_log_chat_ids() -> list[int]:
    return [int(row[0]) for row in await list_private_log_chats()]


async def save_stats_summary_cache(stats: dict):
    """Umumiy statistikani cache jadvaliga saqlaydi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO stats_cache (
                id, chats_count, member_chats, bot_admin_chats, not_member_chats,
                groups_count, channels_count, group_member_chats, channel_member_chats,
                group_admin_chats, channel_admin_chats, users_count, unsafe_ext_count,
                bad_words_count, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                chats_count=excluded.chats_count,
                member_chats=excluded.member_chats,
                bot_admin_chats=excluded.bot_admin_chats,
                not_member_chats=excluded.not_member_chats,
                groups_count=excluded.groups_count,
                channels_count=excluded.channels_count,
                group_member_chats=excluded.group_member_chats,
                channel_member_chats=excluded.channel_member_chats,
                group_admin_chats=excluded.group_admin_chats,
                channel_admin_chats=excluded.channel_admin_chats,
                users_count=excluded.users_count,
                unsafe_ext_count=excluded.unsafe_ext_count,
                bad_words_count=excluded.bad_words_count,
                updated_at=CURRENT_TIMESTAMP
        """, (
            stats.get("chats_count", 0), stats.get("member_chats", 0), stats.get("bot_admin_chats", 0),
            stats.get("not_member_chats", 0), stats.get("groups_count", 0), stats.get("channels_count", 0),
            stats.get("group_member_chats", 0), stats.get("channel_member_chats", 0),
            stats.get("group_admin_chats", 0), stats.get("channel_admin_chats", 0), stats.get("users_count", 0),
            stats.get("unsafe_ext_count", 0), stats.get("bad_words_count", 0),
        ))
        await db.commit()


async def get_stats_summary_cached():
    """Tugma bosilganda faqat cache'dan o'qiladi; cache bo'lmasa SQL count bilan fallback qiladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT chats_count, member_chats, bot_admin_chats, not_member_chats,
                   groups_count, channels_count, group_member_chats, channel_member_chats,
                   group_admin_chats, channel_admin_chats, users_count, unsafe_ext_count,
                   bad_words_count, updated_at
            FROM stats_cache WHERE id=1
        """)
        row = await cursor.fetchone()
    if not row:
        stats = await get_stats_summary()
        stats["updated_at"] = None
        return stats
    keys = [
        "chats_count", "member_chats", "bot_admin_chats", "not_member_chats",
        "groups_count", "channels_count", "group_member_chats", "channel_member_chats",
        "group_admin_chats", "channel_admin_chats", "users_count", "unsafe_ext_count",
        "bad_words_count", "updated_at",
    ]
    return dict(zip(keys, row))


async def rebuild_referral_stats_cache():
    """Referral ssilkalar statistikasi cache'ini chats jadvalidagi oxirgi statuslar asosida yangilaydi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM referral_stats_cache WHERE link_id NOT IN (SELECT id FROM referral_links)")
        await db.execute("""
            INSERT INTO referral_stats_cache (link_id, groups_count, admin_count, member_count, not_member_count, updated_at)
            SELECT
                rl.id,
                COALESCE(SUM(CASE WHEN c.is_bot_admin=1 THEN 1 ELSE 0 END), 0) AS groups_count,
                COALESCE(SUM(CASE WHEN c.is_bot_admin=1 THEN 1 ELSE 0 END), 0) AS admin_count,
                COALESCE(SUM(CASE WHEN COALESCE(c.bot_status, 'unknown') NOT IN ('not_member','left','kicked') THEN 1 ELSE 0 END), 0) AS member_count,
                COALESCE(SUM(CASE WHEN COALESCE(c.bot_status, 'unknown') IN ('not_member','left','kicked') THEN 1 ELSE 0 END), 0) AS not_member_count,
                CURRENT_TIMESTAMP
            FROM referral_links rl
            LEFT JOIN referral_link_chats rlc ON rlc.link_id = rl.id
            LEFT JOIN chats c ON c.chat_id = rlc.chat_id
            GROUP BY rl.id
            ON CONFLICT(link_id) DO UPDATE SET
                groups_count=excluded.groups_count,
                admin_count=excluded.admin_count,
                member_count=excluded.member_count,
                not_member_count=excluded.not_member_count,
                updated_at=CURRENT_TIMESTAMP
        """)
        await db.commit()


async def get_chat_by_id(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT chat_id, title, type, invite_link, is_bot_admin, COALESCE(bot_status, 'unknown')
            FROM chats WHERE chat_id=?
        """, (chat_id,))
        return await cursor.fetchone()


async def get_referral_chat_count(link_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*)
            FROM referral_link_chats rlc
            JOIN chats c ON c.chat_id = rlc.chat_id
            WHERE rlc.link_id=? AND c.is_bot_admin=1
        """, (link_id,))
        row = await cursor.fetchone()
        return int(row[0] or 0)
