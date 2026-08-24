from datetime import datetime
import typing
from typing import Any, Dict
from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent
from src.helpers.fetch_profile import get_user_profile_info_rapidapi
from TikTokLive import TikTokLiveClient
from src.data.db import (get_channel_metrics, 
                         init_db, update_daily_channel_metrics, 
                         update_daily_bot_metrics, 
                         log_command_usage,
                         get_bot_metrics,
                         get_command_logs
                        )
from dotenv import load_dotenv
from src.helpers.monitor import monitor_system_usage, get_daily_averages, get_current_uptime_hours
import asyncio
import discord
from discord.ext import commands, tasks
import discord
import os
import pprint

# Load envs
load_dotenv()
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME", "@TheHollowPianist")
# discord channel webhook
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

#bot token
BOT_TOKEN = os.getenv("BOT_TOKEN", "_")

#hollow logo
# IMPORTANT: if wanted to use, must be inside the function so it's excecuted every time 
# the command is called, otherwise it will be cached and not sent to discord
# hollow_pfp = discord.File("assets/hollow_pfp.png", filename="hollow_pfp.png") 

# we need to activate required intents (events) from discord
# we achieve that by executing .defaullt() config function
intents = discord.Intents.default()
# priviliged intents are non default-activated 
intents.message_content = True #message_content allows the bot to read user messages

bot = commands.Bot(command_prefix="hw ", intents=intents)

# create TikTokLive client  
tt_client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)


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

@tasks.loop(hours=23, minutes=59, seconds=59)
async def update_metrics_loop():
    try:
        #Update channel metrics
        pf_data = await get_user_profile_info_rapidapi(TIKTOK_USERNAME) # Fetch TikTok channel info
        pf_data = typing.cast(Dict[str, Any], pf_data)

        likes = pf_data.get("likes", 0) or 0
        followers = pf_data.get("followers", 0) or 0
        video_count = pf_data.get("video_count", 0) or 0
        engagement_rate = (likes / (video_count * followers)) * 100 if video_count > 0 and followers > 0 else 0.0
        average_likes_per_video = likes / video_count if video_count > 0 else 0.0
            
        await update_daily_channel_metrics(
            tik_tok_likes=likes,
            followers=followers,
            engagement_rate_increment=engagement_rate,
            average_likes_per_video_increment=average_likes_per_video
        )
        
        
        #Update bot metrics
        daily_averages = get_daily_averages(reset=True)
        uptime_hours = get_current_uptime_hours()
        await update_daily_bot_metrics(
            average_cpu_usage=daily_averages["avg_cpu"],
            average_memory_usage=daily_averages["avg_memory"],
            uptime_hours=uptime_hours
        )

    except Exception as e:
        print(f"Failed to update metrics: {e} ('update_metrics_loop()')")

@bot.event
async def on_ready():
    print(f"✅ discord bot: {bot.user}")
    await init_db()  # Initialize the database when the bot is ready

    # protects against desconextions and restarts
    if not update_metrics_loop.is_running():
        update_metrics_loop.start()  # Start the metrics update loop
    if not monitor_system_usage.is_running():
        monitor_system_usage.start()  # Start the system usage monitoring loop (bot metrics)

@bot.command(
        brief="Muestra la latencia del bot e informacion del mismo.",
        help="""Muestra la latencia del bot en milisegundos y la informacion de la aplicacion, 
            incluyendo el ID y el nombre de la app.  

            Parametros:
                - Este comando no recibe argumentos
            """
)
async def ping(ctx):
    try:
        # ctx (Context) cotains all the tracking information
        async with ctx.typing():
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

        # update bd stats and audit logs
        await update_daily_bot_metrics(discord_commands_increment=1,)
        await log_command_usage("ping", ctx.author.name, ctx.channel.name, True)

    except Exception as e:
        print(f"Failed at 'ping': {e}")
        await log_command_usage("ping", ctx.author.name, ctx.channel.name, False)

@bot.command(
    brief="Muestra informacion general del bot y sus comandos.",
    help="""Muestra la fecha de inicio del desarrollo, ID de la app, 
            nombre, prefijo de comando actual y una lista de comandos con descripciones breves  
    
            Parametros:
                - Este comando no recibe argumentos
            """
)
async def info(ctx):
    try:
        async with ctx.typing():
            app_info = await bot.application_info()

        command_list = "".join([f"- `{cmd.name}`: {cmd.brief} \n" for cmd in bot.commands])

        description_text = (
            f"Fecha de inicio del desarrollo: `17 de Agosto de 2026` \n"
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

        # update bd stats (audit logs)
        await update_daily_bot_metrics(discord_commands_increment=1,)
        await log_command_usage("info", ctx.author.name, ctx.channel.name, True)

    except Exception as e:
        print(f"Exception at 'info': {e}")
        await log_command_usage("info", ctx.author.name, ctx.channel.name, False)

@bot.command(
        brief="Cambia el estado y actividad del bot personalizados.",
        help="""Actualiza el estado y actividad del bot segun los parametros que se le pasen.
         
                Parametros:
                    1. Actividad: la actividad que se le asigna al bot.

                        - Solo puede tomar los valores: 
                        "watching" | "playing" | "listening" | "competing"
                        o 
                        "ver" | "jugar" | "escuchar" | "competir"

                        - Ejemplo: hw change_status watching TheHollowPianist

                    2. Estado: el texto que se va a mostrar debajo del nombre del bot.

                        - Puede tomar cualquier texto. Para textos con espacios es OBLIGATORIO
                          el uso de comillas como se muestra acontinuacion:

                        - Ejemplo: hw change_status watching "TheHollowPianist on Tik Tok"

                ------------------------------ para desarrolladores --------------------------"""
)
#@commands.has_permissions(administrator=True)
async def change_status(ctx, state: str, text: str = ""):
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
        await ctx.send("❌ **Actividad no valida. Usa: playing, watching, listening o competing.**")
        return
    if text == "":
        await ctx.send("❌ **El estado no puede estar vacio.**")
        return
    
    try:
        async with ctx.typing():
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=status_map[state_key], 
                    name=f"{text}"
                )
            )

        embed = discord.Embed(
                title=f"Estado y actividad actualizados: \n",
                description=f"Actividad: `{state}` \n Estado: `{text}`",
                color=discord.Color.purple(),
                )

        await ctx.send(embed=embed)

        # update bd stats (audit logs)
        await update_daily_bot_metrics(discord_commands_increment=1,)
        await log_command_usage("change_status", ctx.author.name, ctx.channel.name, True)
        
    except Exception as e:
            print(f"Failed at 'change_status': {e}")
            await log_command_usage("change_status", ctx.author.name, ctx.channel.name, False)

@bot.command()
async def tt_info(ctx, show_id: str = "", force_refresh: str = ""):
    try:
        async with ctx.typing():
            profile_info = await get_user_profile_info_rapidapi(TIKTOK_USERNAME, force_refresh=bool(force_refresh == "-f")) 
        
        if not profile_info:
            await ctx.send(f"❌ No se pudo obtener la informacion de `@{TIKTOK_USERNAME.lstrip('@')}`.")
            return

        description_text = (
            f"**Nombre de perfil:** `{profile_info['nickname']}`\n"
            f"**Biografia:** {profile_info['bio']}\n\n"
            f"**Verificado:** `{'Si' if profile_info['verified'] else 'No'}`\n\n"
            f"**Seguidores:** `{profile_info['followers']:,}`\n"
            f"**Siguiendo:** `{profile_info['following']:,}`\n"
            f"**Me gusta:** `{profile_info['likes']:,}`\n"
            f"**Cantidad de videos:** `{profile_info['video_count']:,}`\n"
            f"**Links en biografía:** `{profile_info['bio_link']}`\n"
            f"**Cuenta privada:** `{profile_info['is_private']}`\n"
        )

        if show_id == "-id":
            description_text += f"**ID de usuario:** `{profile_info['sec_uid']}`\n"

        embed = discord.Embed(
            title=f"Información de perfil de @{profile_info['username']}",
            description=description_text,
            color=discord.Color.purple()
        )

        if profile_info['avatar_url']:
            embed.set_thumbnail(url=profile_info['avatar_url'])

        await ctx.send(embed=embed)

        # update bd stats (audit logs)
        await update_daily_bot_metrics(discord_commands_increment=1,)
        await log_command_usage("tt_info", ctx.author.name, ctx.channel.name, True)

    except Exception as e:
        print(f"Failed at 'tt_info': {e}")
        await log_command_usage("tt_info", ctx.author.name, ctx.channel.name, False)

@bot.command()
async def channel_metrics(ctx, date: str | None = None):
    current_year = datetime.now().year  
    current_month = datetime.now().month  
    # if date is "08-19" it assumes 2026-08-19
    if date and len(date) == 5:
        date = f"{current_year}-{date}"  # Assuming the current year

    #if date is "19" it assumes 2026-08-19
    if date and len(date) == 2:
        date = f"{current_year}-{current_month:02d}-{date}"  # Assuming the current year and month

    try:
        async with ctx.typing():
            ch_metrics = await get_channel_metrics(date=date)

        if not ch_metrics:
            await ctx.send("❌ No se pudo obtener las metricas del canal")
            return

        description_text = (
            f"** >> 🗓️  Fecha:** `{ch_metrics['date']}`\n"   
            f"** >> 👍 Me gusta totales:**            \u200b`{ch_metrics['tiktok_likes']:,}`\n"
            f"** >> 💜 Nuevos seguidores:**           \u200b `{ch_metrics['new_followers']:,}`\n\n"
            f"** >> 📈 Tasa de engagement:**          \u200b `{ch_metrics['engagement_rate']:.2f}%`\n"
            f"** >> 📊 Promedio de likes por video:** \u200b `{ch_metrics['average_likes_per_video']:.2f}`\n\n"

             "-# Estas metricas se actualizan diariamente.\n"

           #"```ansi\n\u001b[1;35m\n```"

        )

        embed = discord.Embed(
            title=f"Metricas diarias del canal {TIKTOK_USERNAME}",
            description=description_text,
            color=discord.Color.purple()
        ) 

        embed.set_thumbnail(url="https://p16-common-sign.tiktokcdn.com/tos-alisg-avt-0068/5186191b98ffacf7eb2eff30b6ced1d2~tplv-tiktokx-cropcenter:1080:1080.jpeg?dr=14579&refresh_token=15cf08f9&x-expires=1787270400&x-signature=kPpBRTtCZlqhWfAjxgQvQuDj634%3D&t=4d5b0474&ps=13740610&shp=a5d48078&shcp=81f88b70&idc=my2")

        await ctx.send(embed=embed)

        # audit logs
        await update_daily_bot_metrics(discord_commands_increment=1)
        await log_command_usage("channel_metrics", ctx.author.name, ctx.channel.name, True)

    except Exception as e:
        print(f"Failed at 'channel_metrics': {e}")
        await log_command_usage("channel_metrics", ctx.author.name, ctx.channel.name, False)

@bot.command()
async def bot_metrics(ctx, date: str | None = None):
    current_year = datetime.now().year  
    current_month = datetime.now().month  
        # if date is "08-19" it assumes 2026-08-19
    if date and len(date) == 5:
            date = f"{current_year}-{date}"  # Assuming the current year
    
        #if date is "19" it assumes 2026-08-19
    if date and len(date) == 2:
            date = f"{current_year}-{current_month:02d}-{date}"  # Assuming the current year and month
    
    try:
        async with ctx.typing():
            bot_metrics = await get_bot_metrics(date=date)
    
            if not bot_metrics:
                await ctx.send("❌ No se pudo obtener las metricas del bot")
                return
        
            cpu_usage = get_daily_averages(reset=False)["avg_cpu"]
            memory_usage = get_daily_averages(reset=False)["avg_memory"]
            
            description_text = (
                f"** >> Fecha:** `{bot_metrics['date']}`\n"   
                f"** >> Comandos ejecutados:**    \u200b`{bot_metrics['discord_commands']:,}`\n"
                f"** >> Uso de CPU medio:**        \u200b `{cpu_usage:.2f} %`\n"
                f"** >> Uso de RAM medio:**          \u200b `{memory_usage:.2f} MB`\n"
                f"** >> Horas de actividad:** \u200b `{get_current_uptime_hours():.1f} h`\n\n"
    
                 "-# Estas metricas se actualizan diariamente.\n"
    
               #"```ansi\n\u001b[1;35m\n```"
    
            )
    
            embed = discord.Embed(
                title=f"Metricas diarias del bot HolowBot",
                description=description_text,
                color=discord.Color.purple()
            ) 
    
            embed.set_thumbnail(url="attachment://hollowBot_pfp.jpg")

            hollowBot_pfp = discord.File("assets/hollowBot_pfp.jpg", filename="hollowBot_pfp.jpg")
            await ctx.send(embed=embed, file=hollowBot_pfp)
    
            # audit logs
            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("bot_metrics", ctx.author.name, ctx.channel.name, True)
    
    except Exception as e:
            print(f"Failed at 'bot_metrics': {e}")
            await log_command_usage("bot_metrics", ctx.author.name, ctx.channel.name, False)
 
@bot.command()
async def bot_command_log(ctx, date: str | None = None):
    current_year = datetime.now().year
    current_month = datetime.now().month
    # if date is "08-19" it assumes 2026-08-19
    if date and len(date) == 5:
        date = f"{current_year}-{date}"  # Assuming the current year
    # if date is "19" it assumes 2026-08-19
    if date and len(date) == 2:
        date = f"{current_year}-{current_month:02d}-{date}"  # Assuming the current year and month
    try:
        async with ctx.typing():
            command_logs = await get_command_logs(date=date)
           
        if not command_logs:
            await ctx.send("❌ No se pudo obtener los registros de comandos.")
            return

        description_text = f"\n".join(
            [
                f"**{log['timestamp'][:8]}** - Comando: `{log['command']}`, Usuario: `{log['author']}`, Canal: `{log['channel']}`, Exitoso: `{log['success']}`"
                for log in command_logs
            ]
        )
        # embed description has a limit of 4096 characters, so we need to split it into multiple pages if necessary
        pages = split_embed_description(description_text)
        for page_number, page in enumerate(pages, start=1):
            title = "Registros de comandos del HollowBot"
            if len(pages) > 1:
                title += f" ({page_number}/{len(pages)})"

            embed = discord.Embed(
                title=title,
                description=page,
                color=discord.Color.purple()
            )

            await ctx.send(embed=embed)

        # audit logs
        await update_daily_bot_metrics(discord_commands_increment=1)
        await log_command_usage("bot_command_log", ctx.author.name, ctx.channel.name, True)
    except Exception as e:
        print(f"Failed at 'bot_command_log': {e}")
        await log_command_usage("bot_command_log", ctx.author.name, ctx.channel.name, False)   
    
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