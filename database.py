import aiosqlite
import logging
from datetime import datetime, timedelta
from config import DB_PATH

logger = logging.getLogger(__name__)


ARCHIVE_EXTENSIONS = [".zip", ".rar", ".7z", ".tar", ".gz"]


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
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(link_id, chat_id),
            FOREIGN KEY(link_id) REFERENCES referral_links(id) ON DELETE CASCADE,
            FOREIGN KEY(chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
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
        CREATE TABLE IF NOT EXISTS panel_admin_permissions (
            user_id INTEGER NOT NULL,
            permission TEXT NOT NULL,
            allowed INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, permission),
            FOREIGN KEY(user_id) REFERENCES panel_admins(user_id) ON DELETE CASCADE
        )
        """)

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


async def get_all_chats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT chat_id, title, type, invite_link, is_bot_admin, COALESCE(bot_status, 'unknown')
            FROM chats
            ORDER BY updated_at DESC
        """)
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


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, first_name, last_name, username, language_code, joined_at
            FROM users
            ORDER BY updated_at DESC
        """)
        return await cursor.fetchall()


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
        return cur.rowcount > 0


async def remove_bad_word(word: str, chat_id: int | None = None) -> bool:
    word = (word or "").strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            cur = await db.execute("DELETE FROM bad_words WHERE word=? AND chat_id IS NULL", (word,))
        else:
            cur = await db.execute("DELETE FROM bad_words WHERE word=? AND chat_id=?", (word, chat_id))
        await db.commit()
        return cur.rowcount > 0


async def list_bad_words(chat_id: int | None = None):
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
        return [r[0] for r in rows]


async def get_settings(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO settings (chat_id) VALUES (?)", (chat_id,))
        await db.commit()
        cursor = await db.execute("""
            SELECT mute_minutes, max_warnings, max_file_mb, delete_service_messages, block_archives
            FROM settings WHERE chat_id=?
        """, (chat_id,))
        row = await cursor.fetchone()
        return {
            "mute_minutes": row[0],
            "max_warnings": row[1],
            "max_file_mb": row[2],
            "delete_service_messages": bool(row[3]),
            "block_archives": bool(row[4]),
        }


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
        return True


async def update_setting(chat_id: int, key: str, value: int):
    allowed = {"mute_minutes", "max_warnings", "max_file_mb", "delete_service_messages", "block_archives"}
    if key not in allowed:
        raise ValueError("Noto‘g‘ri sozlama nomi")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO settings (chat_id) VALUES (?)", (chat_id,))
        await db.execute(f"UPDATE settings SET {key}=?, updated_at=CURRENT_TIMESTAMP WHERE chat_id=?", (value, chat_id))
        await db.commit()


async def add_whitelist_user(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO whitelist (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        await db.commit()


async def remove_whitelist_user(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        await db.commit()


async def list_whitelist(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM whitelist WHERE chat_id=? ORDER BY created_at DESC", (chat_id,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        return await cursor.fetchone() is not None


async def list_unsafe_extensions(chat_id: int | None = None):
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
        return [r[0] for r in rows]


async def add_unsafe_extension(ext: str, chat_id: int | None = None):
    ext = (ext or "").strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO unsafe_extensions (chat_id, ext) VALUES (?, ?)", (chat_id, ext))
        await db.commit()


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


async def get_security_logs(limit: int = 20):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT chat_id, user_id, action, reason, file_name, created_at
            FROM security_logs
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return await cursor.fetchall()


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


async def track_referral_chat(code: str, chat_id: int) -> bool:
    link = await get_referral_link_by_code(code)
    if not link:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO referral_link_chats (link_id, chat_id) VALUES (?, ?)",
            (link[0], chat_id)
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
                COUNT(DISTINCT rlc.chat_id) AS groups_count,
                COALESCE(SUM(CASE WHEN c.is_bot_admin=1 THEN 1 ELSE 0 END), 0) AS admin_count,
                rl.created_at
            FROM referral_links rl
            LEFT JOIN referral_link_chats rlc ON rlc.link_id = rl.id
            LEFT JOIN chats c ON c.chat_id = rlc.chat_id
            GROUP BY rl.id
            ORDER BY rl.id DESC
        """)
        return await cursor.fetchall()


async def get_referral_chats(link_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT c.chat_id, c.title, c.type, c.is_bot_admin, COALESCE(c.bot_status, 'unknown'), rlc.added_at
            FROM referral_link_chats rlc
            JOIN chats c ON c.chat_id = rlc.chat_id
            WHERE rlc.link_id=?
            ORDER BY rlc.added_at DESC
        """, (link_id,))
        return await cursor.fetchall()


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
        expires_at = (datetime.now() + timedelta(days=int(expires_days))).strftime("%Y-%m-%d %H:%M:%S")
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
        expires_at = (datetime.now() + timedelta(days=int(expires_days))).strftime("%Y-%m-%d %H:%M:%S")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE panel_admins SET expires_at=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (expires_at, user_id))
        await db.commit()


async def disable_expired_panel_admins() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            UPDATE panel_admins
            SET is_active=0, updated_at=CURRENT_TIMESTAMP
            WHERE is_active=1 AND expires_at IS NOT NULL AND datetime(expires_at) <= datetime('now')
        """)
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
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            await db.execute("DELETE FROM bot_private_settings WHERE key='private_log_chat_id'")
        else:
            await db.execute("""
                INSERT INTO bot_private_settings (key, value)
                VALUES ('private_log_chat_id', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (str(chat_id),))
        await db.commit()


async def get_private_log_chat_id() -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM bot_private_settings WHERE key='private_log_chat_id'")
        row = await cur.fetchone()
        if not row or not row[0]:
            return None
        try:
            return int(row[0])
        except ValueError:
            return None
