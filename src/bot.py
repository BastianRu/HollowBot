import asyncio
import typing
from typing import Any, Dict

import discord
from discord.ext import commands, tasks

from src.commands import register_commands
from src.config import BOT_TOKEN, CURRENT_VER, TIKTOK_USERNAME
from src.infrastructure.database import (
    get_bot_metrics,
    get_channel_metrics,
    get_command_logs,
    init_db,
    log_command_usage,
    update_daily_bot_metrics,
    update_daily_channel_metrics,
)
from src.integrations.tiktok.profile_fetcher import get_user_profile_info_rapidapi
from src.monitoring.system import get_current_uptime_hours, get_daily_averages, monitor_system_usage


# Discord needs explicit message content intent for text-based commands.
intents = discord.Intents.default()
intents.message_content = True

# Bot instance and simple runtime metadata used by command handlers.
bot = commands.Bot(command_prefix="hw ", intents=intents)
bot.current_version = CURRENT_VER
bot.tiktok_username = TIKTOK_USERNAME


def split_embed_description(text: str, limit: int = 4000) -> list[str]:
    pages: list[str] = []
    current_page = ""

    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current_page:
                pages.append(current_page)
                current_page = ""
            pages.extend(line[index:index + limit] for index in range(0, len(line), limit))
        elif len(current_page) + len(line) > limit:
            pages.append(current_page)
            current_page = line
        else:
            current_page += line

    if current_page:
        pages.append(current_page)

    return pages or [""]


@bot.event
async def on_ready():
    print(f"✅ discord bot: {bot.user}")
    await init_db()

    if not update_metrics_loop.is_running():
        update_metrics_loop.start()
    if not monitor_system_usage.is_running():
        monitor_system_usage.start()


# Collect daily TikTok and bot metrics once per day to keep the database useful without extra complexity.
@tasks.loop(hours=23, minutes=59, seconds=59)
async def update_metrics_loop():
    try:
        pf_data = await get_user_profile_info_rapidapi(TIKTOK_USERNAME)
        pf_data = typing.cast(Dict[str, Any], pf_data or {})

        likes = pf_data.get("likes", 0) or 0
        followers = pf_data.get("followers", 0) or 0
        video_count = pf_data.get("video_count", 0) or 0
        engagement_rate = (likes / (video_count * followers)) * 100 if video_count > 0 and followers > 0 else 0.0
        average_likes_per_video = likes / video_count if video_count > 0 else 0.0

        await update_daily_channel_metrics(
            tik_tok_likes=likes,
            followers=followers,
            engagement_rate_increment=engagement_rate,
            average_likes_per_video_increment=average_likes_per_video,
        )

        daily_averages = get_daily_averages(reset=True)
        uptime_hours = get_current_uptime_hours()
        await update_daily_bot_metrics(
            average_cpu_usage=daily_averages["avg_cpu"],
            average_memory_usage=daily_averages["avg_memory"],
            uptime_hours=uptime_hours,
        )
    except Exception as e:
        print(f"Failed to update metrics: {e} ('update_metrics_loop()')")


register_commands(bot)


async def start_bot():
    try:
        await bot.start(BOT_TOKEN)
    except Exception as e:
        print(f"failed to initialize HollowBot: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(start_bot())