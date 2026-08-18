from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent
from src.helpers.fetch_profile import get_user_profile_info
from TikTokLive import TikTokLiveClient
from dotenv import load_dotenv
import asyncio
import discord
from discord.ext import commands
import discord
import os
import pprint

# Load envs
load_dotenv()
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "@TheHollowPianist")
# discord channel webhook
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

BOT_TOKEN = os.getenv("BOT_TOKEN")

# we need to activate required intents (events) from discord
# we achieve that by executing .defaullt() config function
intents = discord.Intents.default()
# priviliged intents are non default-activated 
intents.message_content = True #message_content allows the bot to read user messages

bot = commands.Bot(command_prefix="hw ", intents=intents)

# create TikTokLive client  
tt_client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)

@bot.event
async def on_ready():
    print(f"✅ discord bot: {bot.user}")

@bot.command()
async def ping(ctx):
    try:
        # ctx (Context) cotains all the tracking information
        app_info = await bot.application_info()
        latency_ms = round(bot.latency * 1000)

        description_text = (
            f"⚡ **Latencia del bot:** `{latency_ms}ms`\n"
            f"📍 **Region del bot:** `Colombia`\n\n"
            f"ID de la aplicacion: `{app_info.id}`\n"
            f"Nombre de la app: `{app_info.name}`"
        )

        embed = discord.Embed(
            title="Estoy vivo y resonando! 💜 HollowBot",
            description=description_text,
            color=discord.Color.purple(),
        )

        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Failed at 'ping': {e}")

@bot.command()
async def info(ctx):
    try:
        app_info = await bot.application_info()

        command_list = "".join([f"- `{cmd.name}` \n" for cmd in bot.commands])

        description_text = (
            f"Fecha de Nacimiento: `17 de Agosto de 2026` \n"
            f"ID de la aplicacion: `{app_info.id}`\n"
            f"Nombre de la app: `{app_info.name}`\n"
            f"Prefijo de comando actual: `{bot.command_prefix}` \n\n"
            f"Lista de comandos: \n {command_list}"
        )

        embed = discord.Embed(
                title=f"HollowBot v{os.getenv('CURRENT_VER')}", #X.Y.Z versioning
                description=description_text,
                color=discord.Color.purple(),
            )
        
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Exception at 'info': {e}")

@bot.command()
#@commands.has_permissions(administrator=True)
async def change_status(ctx, state: str, text: str):
    # state could be "watching" | "playing" | "listening" | "competing" 
    status_map = {
        "playing": discord.ActivityType.playing,
        "jugar": discord.ActivityType.playing,
        
        "watching": discord.ActivityType.watching,
        "ver": discord.ActivityType.watching,
        
        "listening": discord.ActivityType.listening,
        "escuchar": discord.ActivityType.listening,
        
        "competing": discord.ActivityType.competing,
        "competir": discord.ActivityType.competing
    }

    state_key = state.lower()
    if state_key not in status_map:
        await ctx.send("❌ **Estado no valido. Usa: playing, watching, listening o competing.**")
        return
    
    try:

        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=status_map[state_key], 
                name=f"{text}"
                )
        )

        embed = discord.Embed(
                title=f"Estado actualizado a `{state}`\n",
                description=f"{text}",
                color=discord.Color.purple(),
                )

        await ctx.send(embed=embed)
        
    except Exception as e:
            print(f"Failed at 'change_status': {e}")

@bot.command()
async def hollow_info(ctx, username: str = TIKTOK_USERNAME):
    try:
        async with ctx.typing():
            profile_info = await get_user_profile_info(username)
        
        if not profile_info:
            await ctx.send(f"❌ No se pudo obtener la informacion de `@{username.lstrip('@')}`.")
            return

        description_text = (
            f"**Nombre de perfil:** `{profile_info['nickname']}`\n"
            f"**Biografia:** {profile_info['bio']}\n\n"
            f"**Verificado:** `{'Si' if profile_info['verified'] else 'No'}`\n\n"
            f"**Seguidores:** `{profile_info['followers']:,}`\n"
            f"**Siguiendo:** `{profile_info['following']:,}`\n"
            f"**Me gusta:** `{profile_info['likes']:,}`\n"
            f"**Cantidad de videos:** `{profile_info['video_count']:,}`\n"
        )

        embed = discord.Embed(
            title=f"Información de perfil de @{profile_info['username']}",
            description=description_text,
            color=discord.Color.purple()
        )

        if profile_info['avatar_url']:
            embed.set_thumbnail(url=profile_info['avatar_url'])

        await ctx.send(embed=embed)

    except Exception as e:
        print(f"Failed at 'hollow_info': {e}")

# init bot
async def start_bot():
    try:
        # Using await keeps the function active as long as the bot runs
        await bot.start(BOT_TOKEN)
    except Exception as e:
        print(f"failed to initialize HollowBot: {e}")
    finally:
        # Ensures everything cleans up if the bot disconnects or crashes
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(start_bot())