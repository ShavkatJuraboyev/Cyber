import asyncio
import logging

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from database import (
    get_all_chats,
    update_chat_bot_status,
    get_stats_summary,
    save_stats_summary_cache,
    rebuild_referral_stats_cache,
)

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 30 * 60
REFRESH_CONCURRENCY = 12


async def _refresh_one_chat_status(bot, bot_id: int, chat_id: int) -> tuple[int, str]:
    try:
        member = await bot.get_chat_member(chat_id, bot_id)
        status = getattr(member.status, "value", str(member.status))
        is_admin = 1 if member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} else 0
        await update_chat_bot_status(chat_id, is_admin, status)
        return is_admin, status
    except (TelegramForbiddenError, TelegramBadRequest):
        await update_chat_bot_status(chat_id, 0, "not_member")
        return 0, "not_member"
    except Exception as exc:
        logger.warning("Status cache yangilashda xato. chat_id=%s: %s", chat_id, exc)
        await update_chat_bot_status(chat_id, 0, "unknown")
        return 0, "unknown"


async def refresh_stats_cache_once(bot) -> None:
    """10 000+ chatni fon rejimida tekshiradi va natijani cache jadvallariga yozadi."""
    bot_id = (await bot.me()).id
    chats = await get_all_chats()
    semaphore = asyncio.Semaphore(REFRESH_CONCURRENCY)

    async def worker(chat_id: int):
        async with semaphore:
            return await _refresh_one_chat_status(bot, bot_id, chat_id)

    if chats:
        await asyncio.gather(*(worker(int(chat[0])) for chat in chats), return_exceptions=True)

    stats = await get_stats_summary()
    await save_stats_summary_cache(stats)
    await rebuild_referral_stats_cache()
    logger.info("Statistika cache yangilandi: chats=%s admin=%s", stats.get("chats_count"), stats.get("bot_admin_chats"))


async def stats_cache_loop(bot) -> None:
    """Bot ishlashi davomida statistikani har 30 daqiqada yangilab turadi."""
    await asyncio.sleep(5)
    while True:
        try:
            await refresh_stats_cache_once(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Statistika cache loop xatoga uchradi")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
