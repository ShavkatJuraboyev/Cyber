import aiosqlite

DB_PATH = "chat.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Chats
        await db.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            type TEXT,
            is_admin INTEGER DEFAULT 0
        )
        """)
        # Bad words (global yoki chatga xos)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bad_words (
            chat_id INTEGER,           -- NULL/None bo‘lsa global
            word TEXT NOT NULL,
            UNIQUE(chat_id, word)
        )
        """)
        # Settings (masalan mute_durations)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER PRIMARY KEY, 
            mute_minutes INTEGER DEFAULT 10
        )
        """)
        # whitelist jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS whitelist (
            chat_id INTEGER,
            user_id INTEGER,
            UNIQUE(chat_id, user_id)
        )
        """)
        await db.commit()


async def add_or_update_chat(chat_id: int, title: str, chat_type: str, is_admin: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO chats (chat_id, title, type, is_admin)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title=excluded.title,
            type=excluded.type,
            is_admin=excluded.is_admin
        """, (chat_id, title, chat_type, is_admin))
        await db.commit()

# ========== Whitelist foydalanuvchilar ==========
async def add_whitelist_user(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO whitelist (chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        await db.commit()

async def get_all_chats():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT chat_id, title, type, is_admin FROM chats")
        return await cursor.fetchall()


# ---------- Bad words ----------
async def add_bad_word(word: str, chat_id: int | None = None):
    word = word.strip().lower()
    if not word:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO bad_words (chat_id, word) VALUES (?, ?)", (chat_id, word))
        await db.commit()

async def remove_bad_word(word: str, chat_id: int | None = None):
    word = word.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bad_words WHERE word=? AND (chat_id IS ? OR chat_id=?)",
                         (word, None if chat_id is None else chat_id, chat_id))
        await db.commit()

async def list_bad_words(chat_id: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        # Global + chatga xos birga
        if chat_id is None:
            cursor = await db.execute("SELECT word FROM bad_words WHERE chat_id IS NULL ORDER BY word")
        else:
            cursor = await db.execute("""
                SELECT word FROM bad_words 
                WHERE chat_id IS NULL
                   OR chat_id = ?
                GROUP BY word
                ORDER BY word
            """, (chat_id,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

# ---------- Settings ----------
async def get_mute_minutes(chat_id: int | None) -> int:
    # Chat bo‘yicha sozlama bo‘lmasa default 10
    async with aiosqlite.connect(DB_PATH) as db:
        if chat_id is None:
            return 10
        cursor = await db.execute("SELECT mute_minutes FROM settings WHERE chat_id=?", (chat_id,))
        row = await cursor.fetchone()
        return row[0] if row else 10

async def set_mute_minutes(chat_id: int, minutes: int):
    minutes = max(1, min(4320, int(minutes)))  # 1 daq - 3 kun
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT INTO settings (chat_id, mute_minutes)
        VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET mute_minutes=excluded.mute_minutes
        """, (chat_id, minutes))
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
        cursor = await db.execute("SELECT user_id FROM whitelist WHERE chat_id=?", (chat_id,))
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM whitelist WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        return await cursor.fetchone() is not None

