import aiosqlite
import datetime

# Create a database connection and initialize the table if it doesn't exist
async def init_db():
    try:
        async with aiosqlite.connect("bot_metrics.db") as db:
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
            """)
            await db.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")

# function to update the daily metrics for TikTok comments
async def update_daily_channel_metrics(
    tik_tok_likes=0,
    followers=0,
    engagement_rate_increment=0.0,
    average_likes_per_video_increment=0.0
    ):
    today = datetime.date.today().isoformat() # generates "2026-08-18"
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat() # generates "2026-08-17"
    try:
        await init_db()  # Ensure the database and tables are initialized before updating
    
        async with aiosqlite.connect("bot_metrics.db") as db:
            async with db.execute("""
                SELECT followers, tiktok_likes FROM channel_daily_metrics WHERE date = ?
                """, (yesterday,)) as cursor:
                result = await cursor.fetchone()
                yesterday_followers, yesterday_likes = result if result else (None, None)

            new_followers = max(0, followers - yesterday_followers) if yesterday_followers is not None else 0
            likes_increment = max(0, tik_tok_likes - yesterday_likes) if yesterday_likes is not None else 0

            await db.execute("""
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
            """, (
                today,
                tik_tok_likes,
                likes_increment,
                followers,
                new_followers,
                engagement_rate_increment,
                average_likes_per_video_increment,
            ))
            await db.commit()
    except Exception as e:
        print(f"Error updating daily channel metrics: {e}")

# function to update the daily metrics for bot performance
async def update_daily_bot_metrics(
    discord_commands_increment=0,
    average_cpu_usage=0.0,
    average_memory_usage=0.0,
    uptime_hours=0.0
    ):
    today = datetime.date.today().isoformat() # generates "2026-08-18"
    try:
        async with aiosqlite.connect("bot_metrics.db") as db:
            # INSERT OR IGNORE to ensure there's a row for today, then UPDATE to increment the counter 
            await db.execute("""
                INSERT OR IGNORE INTO bot_daily_metrics (date) VALUES (?)
            """, (today,))
            
            await db.execute("""
                UPDATE bot_daily_metrics 
                SET discord_commands = discord_commands + ?, 
                average_cpu_usage = average_cpu_usage + ?, 
                average_memory_usage = average_memory_usage + ?, 
                uptime_hours = uptime_hours + ?
                WHERE date = ?
            """, (discord_commands_increment, 
                average_cpu_usage, 
                average_memory_usage, 
                uptime_hours, 
                today))
            await db.commit()
    except Exception as e:
        print(f"Error updating daily bot metrics: {e}")

async def log_command_usage(command: str, author: str, channel: str, success: bool):
    today = datetime.date.today().isoformat() # generates "2026-08-18"
    timestamp = datetime.datetime.now().time().isoformat() # generates "12:34:56"
    try:
        async with aiosqlite.connect("bot_metrics.db") as db:
            await db.execute("""
                INSERT INTO bot_commands (date, command, author, channel, timestamp, success) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (today, command, author, channel, timestamp, int(success)))
            await db.commit()
    except Exception as e:
        print(f"Error logging command usage: {e}")

# get channel daily metrics 
async def get_channel_metrics(date: str | None = None):
    date = date or datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect("bot_metrics.db") as db:
            async with db.execute("""
                SELECT * FROM channel_daily_metrics WHERE date = ?
            """, (date,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "date": row[0],
                        "tiktok_likes": row[1],
                        "tiktok_likes_increment": row[2],
                        "followers": row[3],
                        "new_followers": row[4],
                        "engagement_rate": row[5],
                        "average_likes_per_video": row[6]
                    }
                else:
                    return None
    except Exception as e:
        print(f"Error fetching daily channel metrics: {e}")
        return None

async def get_bot_metrics(date: str | None = None):
    date = date or datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect("bot_metrics.db") as db:
            async with db.execute("""
                SELECT * FROM bot_daily_metrics WHERE date = ?
            """, (date,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "date": row[0],
                        "discord_commands": row[1],
                        "average_cpu_usage": row[2],
                        "average_memory_usage": row[3],
                        "uptime_hours": row[4]
                    }
                else:
                    return None
    except Exception as e:
        print(f"Error fetching daily bot metrics: {e}")
        return None

async def get_command_logs(date: str | None = None):
    date = date or datetime.date.today().isoformat()
    try:
        async with aiosqlite.connect("bot_metrics.db") as db:
            async with db.execute("""
                SELECT * FROM bot_commands WHERE date = ?
            """, (date,)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "date": row[1],
                        "command": row[2],
                        "author": row[3],
                        "channel": row[4],
                        "timestamp": row[5],
                        "success": bool(row[6])
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
        async with aiosqlite.connect("bot_metrics.db") as db:
            await db.executescript(script)
            await db.commit()
    except Exception as e:
        print(f"Error restarting bot_commands table: {e}")
    

if __name__ == "__main__":
    import asyncio
    asyncio.run(restart_table_bot_commands())
    #print("restarted tables")