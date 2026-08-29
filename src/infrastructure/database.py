import datetime

import aiosqlite

from src.config import DATABASE_PATH


async def init_db():
    # Ensure the SQLite schema exists before any commands or metrics write to it.
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS bot_daily_metrics (
                    date TEXT PRIMARY KEY,
                    discord_commands INTEGER DEFAULT 0,
                    average_cpu_usage REAL DEFAULT 0.0,
                    average_memory_usage REAL DEFAULT 0.0,
                    uptime_hours REAL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS bot_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    command TEXT NOT NULL,
                    author TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    success INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS channel_daily_metrics (
                    date TEXT PRIMARY KEY,
                    tiktok_likes INTEGER DEFAULT 0,
                    tiktok_likes_increment INTEGER DEFAULT 0,
                    followers INTEGER DEFAULT 0,
                    new_followers INTEGER DEFAULT 0,
                    engagement_rate REAL DEFAULT 0.0,
                    average_likes_per_video REAL DEFAULT 0.0
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    estimated_hours REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    status TEXT NOT NULL DEFAULT 'pending',
                    parent_id INTEGER,
                    is_subtask BOOLEAN DEFAULT 0,
                    block_number INTEGER,
                    total_blocks INTEGER,
                    user_id TEXT
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id TEXT PRIMARY KEY,
                    timezone TEXT NOT NULL DEFAULT 'America/Bogota',
                    trench_days TEXT NOT NULL DEFAULT '[0, 2, 4]',
                    deep_work_days TEXT NOT NULL DEFAULT '[1, 3]',
                    w_trench REAL NOT NULL DEFAULT 0.2,
                    w_deep REAL NOT NULL DEFAULT 1.5,
                    w_weekend_default REAL NOT NULL DEFAULT 1.0,
                    max_trench_hours REAL NOT NULL DEFAULT 1.5,
                    block_size REAL NOT NULL DEFAULT 2.0,
                    weekend_mode TEXT NOT NULL DEFAULT 'HARD_WORK_BALANCED',
                    notification_channel_id INTEGER
                );
            """)
            await db.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")


async def update_daily_channel_metrics(
    tik_tok_likes=0,
    followers=0,
    engagement_rate_increment=0.0,
    average_likes_per_video_increment=0.0,
):
    # Daily channel stats compare the current values with the previous day to calculate deltas.
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    try:
        await init_db()

        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                """
                SELECT followers, tiktok_likes FROM channel_daily_metrics WHERE date = ?
                """,
                (yesterday,),
            ) as cursor:
                result = await cursor.fetchone()
                yesterday_followers, yesterday_likes = result if result else (None, None)

            new_followers = max(0, followers - yesterday_followers) if yesterday_followers is not None else 0
            likes_increment = max(0, tik_tok_likes - yesterday_likes) if yesterday_likes is not None else 0

            await db.execute(
                """
                INSERT INTO channel_daily_metrics (
                    date, tiktok_likes, tiktok_likes_increment, followers,
                    new_followers, engagement_rate, average_likes_per_video
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    tiktok_likes = excluded.tiktok_likes,
                    tiktok_likes_increment = excluded.tiktok_likes_increment,
                    followers = excluded.followers,
                    new_followers = excluded.new_followers,
                    engagement_rate = excluded.engagement_rate,
                    average_likes_per_video = excluded.average_likes_per_video
            """,
                (
                    today,
                    tik_tok_likes,
                    likes_increment,
                    followers,
                    new_followers,
                    engagement_rate_increment,
                    average_likes_per_video_increment,
                ),
            )
            await db.commit()
    except Exception as e:
        print(f"Error updating daily channel metrics: {e}")


async def update_daily_bot_metrics(
    discord_commands_increment=0,
    average_cpu_usage=0.0,
    average_memory_usage=0.0,
    uptime_hours=0.0,
):
    today = datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO bot_daily_metrics (date) VALUES (?)
            """,
                (today,),
            )

            await db.execute(
                """
                UPDATE bot_daily_metrics
                SET discord_commands = discord_commands + ?,
                average_cpu_usage = average_cpu_usage + ?,
                average_memory_usage = average_memory_usage + ?,
                uptime_hours = uptime_hours + ?
                WHERE date = ?
            """,
                (
                    discord_commands_increment,
                    average_cpu_usage,
                    average_memory_usage,
                    uptime_hours,
                    today,
                ),
            )
            await db.commit()
    except Exception as e:
        print(f"Error updating daily bot metrics: {e}")


async def log_command_usage(command: str, author: str, channel: str, success: bool):
    today = datetime.date.today().isoformat()
    timestamp = datetime.datetime.now().time().isoformat()
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(
                """
                INSERT INTO bot_commands (date, command, author, channel, timestamp, success)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (today, command, author, channel, timestamp, int(success)),
            )
            await db.commit()
    except Exception as e:
        print(f"Error logging command usage: {e}")


async def get_channel_metrics(date: str | None = None):
    date = date or datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                """
                SELECT * FROM channel_daily_metrics WHERE date = ?
            """,
                (date,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "date": row[0],
                        "tiktok_likes": row[1],
                        "tiktok_likes_increment": row[2],
                        "followers": row[3],
                        "new_followers": row[4],
                        "engagement_rate": row[5],
                        "average_likes_per_video": row[6],
                    }
                return None
    except Exception as e:
        print(f"Error fetching daily channel metrics: {e}")
        return None


async def get_bot_metrics(date: str | None = None):
    date = date or datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                """
                SELECT * FROM bot_daily_metrics WHERE date = ?
            """,
                (date,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "date": row[0],
                        "discord_commands": row[1],
                        "average_cpu_usage": row[2],
                        "average_memory_usage": row[3],
                        "uptime_hours": row[4],
                    }
                return None
    except Exception as e:
        print(f"Error fetching daily bot metrics: {e}")
        return None


async def get_command_logs(date: str | None = None):
    date = date or datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                """
                SELECT * FROM bot_commands WHERE date = ?
            """,
                (date,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "date": row[1],
                        "command": row[2],
                        "author": row[3],
                        "channel": row[4],
                        "timestamp": row[5],
                        "success": bool(row[6]),
                    }
                    for row in rows
                ]
    except Exception as e:
        print(f"Error fetching command logs: {e}")
        return []


async def restart_table_bot_commands():
    try:
        script = """
        DROP TABLE IF EXISTS bot_commands;

        CREATE TABLE IF NOT EXISTS bot_commands (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT NOT NULL,
                            command TEXT NOT NULL,
                            author TEXT NOT NULL,
                            channel TEXT NOT NULL,
                            timestamp TEXT NOT NULL,
                            success INTEGER DEFAULT 0
                        );

        DROP TABLE IF EXISTS channel_daily_metrics;

        CREATE TABLE IF NOT EXISTS channel_daily_metrics (
                            date TEXT PRIMARY KEY,
                            tiktok_likes INTEGER DEFAULT 0,
                            tiktok_likes_increment INTEGER DEFAULT 0,
                            followers INTEGER DEFAULT 0,
                            new_followers INTEGER DEFAULT 0,
                            engagement_rate REAL DEFAULT 0.0,
                            average_likes_per_video REAL DEFAULT 0.0
                        );
        """
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.executescript(script)
            await db.commit()
    except Exception as e:
        print(f"Error restarting bot_commands table: {e}")


async def reset_autotask_tables():
    """Reset only AutoTask-related tables. Use this when task data is corrupted or stale."""
    try:
        script = """
        DROP TABLE IF EXISTS tasks;
        DROP TABLE IF EXISTS user_settings;

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            due_date TEXT NOT NULL,
            estimated_hours REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'pending',
            parent_id INTEGER,
            is_subtask BOOLEAN DEFAULT 0,
            block_number INTEGER,
            total_blocks INTEGER,
            user_id TEXT
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            timezone TEXT NOT NULL DEFAULT 'America/Bogota',
            trench_days TEXT NOT NULL DEFAULT '[0, 2, 4]',
            deep_work_days TEXT NOT NULL DEFAULT '[1, 3]',
            w_trench REAL NOT NULL DEFAULT 0.2,
            w_deep REAL NOT NULL DEFAULT 1.5,
            w_weekend_default REAL NOT NULL DEFAULT 1.0,
            max_trench_hours REAL NOT NULL DEFAULT 1.5,
            block_size REAL NOT NULL DEFAULT 2.0,
            weekend_mode TEXT NOT NULL DEFAULT 'HARD_WORK_BALANCED',
            notification_channel_id INTEGER
        );
        """
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.executescript(script)
            await db.commit()
    except Exception as e:
        print(f"Error resetting AutoTask tables: {e}")


async def repair_database():
    """Safe recovery helper for the most common SQLite drift scenarios."""
    await reset_autotask_tables()
    await restart_table_bot_commands()
    await init_db()


if __name__ == "__main__":
    import asyncio

    asyncio.run(repair_database())
