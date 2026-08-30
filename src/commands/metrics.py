from datetime import datetime

import discord

from src.config import TIKTOK_USERNAME
from src.infrastructure.database import (
    get_bot_metrics,
    get_channel_metrics,
    get_command_logs,
    log_command_usage,
    update_daily_bot_metrics,
)
from src.integrations.tiktok.profile_fetcher import get_user_profile_info_rapidapi
from src.monitoring.system import get_current_uptime_hours, get_daily_averages


def register_metrics_commands(bot):
    # TikTok profile command: fetches public channel data and sends a formatted embed.
    @bot.command(brief="Muestra informacion del perfil de TikTok del canal",
                 help="""Muestra informacion del perfil de TikTok del canal, incluyendo nombre de usuario, biografia,
                    cantidad de seguidores, cantidad de videos, cantidad de likes y si la cuenta esta verificada o es privada.
                    Por defecto, se refresca cada 8 horas.

                    Parametros (banderas opcionales):
                        - `-id`: Muestra el ID de usuario de TikTok en la respuesta.
                        - `-f`: Fuerza la actualizacion de la informacion del perfil desde API.
                        ALERTA: Este parametro se debe usar con precaucion, ya que depende de un servicio externo con limitaciones de uso y puede generar errores si se usa en exceso. Se recomienda usarlo solo cuando sea necesario.
                    """
                )
    async def tt_info(ctx, show_id: str = "", force_refresh: str = ""):
        try:
            async with ctx.typing():
                profile_info = await get_user_profile_info_rapidapi(
                    TIKTOK_USERNAME,
                    force_refresh=bool(force_refresh == "-f"),
                )

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
                f"**Links en biografía:** {profile_info['bio_link']}\n"
                f"**Cuenta privada:** `{'Si' if profile_info['is_private'] else 'No'}`\n"
            )

            if show_id == "-id":
                description_text += f"**ID de usuario:** `{profile_info['sec_uid']}`\n"

            embed = discord.Embed(
                title=f"Información de perfil de @{profile_info['username']}",
                description=description_text,
                color=discord.Color.purple(),
            )

            if profile_info["avatar_url"]:
                embed.set_thumbnail(url=profile_info["avatar_url"])

            await ctx.send(embed=embed)
            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("tt_info", ctx.author.name, ctx.channel.name, True)

        except Exception as e:
            print(f"Failed at 'tt_info': {e}")
            await log_command_usage("tt_info", ctx.author.name, ctx.channel.name, False)

    @bot.command(brief="Muestra metricas diarias del canal de TikTok",
                help="""Muestra metricas diarias del canal de TikTok, incluyendo cantidad de likes totales, nuevos seguidores,
                    tasa de engagement y promedio de likes por video. Por defecto, se muestran las metricas del dia actual.

                    Parametros:
                        - `mm-dd`: Muestra las metricas del canal para la fecha especificada en formato mes-dia (ejemplo: 03-15 para el 15 de marzo del año actual).
                        - `dd`: Muestra las metricas del canal para el dia especificado en
                            formato dia (ejemplo: 15 para el 15 del mes actual).
                        Si no se especifica ninguna fecha, se muestran las metricas del dia actual.    
                    """
                )
    async def channel_metrics(ctx, date: str | None = None):
        current_year = datetime.now().year
        current_month = datetime.now().month

        if date and len(date) == 5:
            date = f"{current_year}-{date}"
        if date and len(date) == 2:
            date = f"{current_year}-{current_month:02d}-{date}"

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
            )

            embed = discord.Embed(
                title=f"Metricas diarias del canal {TIKTOK_USERNAME}",
                description=description_text,
                color=discord.Color.purple(),
            )

            embed.set_thumbnail(
                url="https://p16-common-sign.tiktokcdn.com/tos-alisg-avt-0068/5186191b98ffacf7eb2eff30b6ced1d2~tplv-tiktokx-cropcenter:1080:1080.jpeg?dr=14579&refresh_token=15cf08f9&x-expires=1787270400&x-signature=kPpBRTtCZlqhWfAjxgQvQuDj634%3D&t=4d5b0474&ps=13740610&shp=a5d48078&shcp=81f88b70&idc=my2"
            )

            await ctx.send(embed=embed)
            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("channel_metrics", ctx.author.name, ctx.channel.name, True)

        except Exception as e:
            print(f"Failed at 'channel_metrics': {e}")
            await log_command_usage("channel_metrics", ctx.author.name, ctx.channel.name, False)

    @bot.command(brief="Muestra metricas diarias del bot", 
                 help="""Muestra metricas diarias del bot, incluyendo cantidad de comandos ejecutados, uso de CPU y RAM, y horas de actividad.

                 Parametros:
                        - `mm-dd`: Muestra las metricas del bot para la fecha especificada en formato mes-dia (ejemplo: 03-15 para el 15 de marzo del año actual).
                        - `dd`: Muestra las metricas del bot para el dia especificado en
                            formato dia (ejemplo: 15 para el 15 del mes actual).
                    Si no se especifica ninguna fecha, se muestran las metricas del dia actual
                 """
                 )
    async def bot_metrics(ctx, date: str | None = None):
        current_year = datetime.now().year
        current_month = datetime.now().month

        if date and len(date) == 5:
            date = f"{current_year}-{date}"
        if date and len(date) == 2:
            date = f"{current_year}-{current_month:02d}-{date}"

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
            )

            embed = discord.Embed(
                title="Metricas diarias del bot HolowBot",
                description=description_text,
                color=discord.Color.purple(),
            )

            embed.set_thumbnail(url="attachment://hollowBot_pfp.jpg")
            hollow_bot_pfp = discord.File("assets/hollowBot_pfp.jpg", filename="hollowBot_pfp.jpg")
            await ctx.send(embed=embed, file=hollow_bot_pfp)

            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("bot_metrics", ctx.author.name, ctx.channel.name, True)

        except Exception as e:
            print(f"Failed at 'bot_metrics': {e}")
            await log_command_usage("bot_metrics", ctx.author.name, ctx.channel.name, False)

    @bot.command(brief="Muestra los registros de comandos ejecutados por el bot",
                help="""Muestra los registros de comandos ejecutados por el bot, incluyendo el comando ejecutado, el usuario que lo ejecuto, el canal donde se ejecuto y si fue exitoso o no.
                Parametros:
                    - `mm-dd`: Muestra los registros de comandos para la fecha especificada en formato mes-dia (ejemplo: 03-15 para el 15 de marzo del año actual).
                    - `dd`: Muestra los registros de comandos para el dia especificado en
                        formato dia (ejemplo: 15 para el 15 del mes actual).
                Si no se especifica ninguna fecha, se muestran los registros de comandos del dia actual.
                """
                 )
    async def bot_command_log(ctx, date: str | None = None):
        current_year = datetime.now().year
        current_month = datetime.now().month

        if date and len(date) == 5:
            date = f"{current_year}-{date}"
        if date and len(date) == 2:
            date = f"{current_year}-{current_month:02d}-{date}"

        try:
            async with ctx.typing():
                command_logs = await get_command_logs(date=date)

            if not command_logs:
                await ctx.send("❌ No se pudo obtener los registros de comandos.")
                return

            description_text = "\n".join(
                [
                    f"**{log['timestamp'][:8]}** - Comando: `{log['command']}`, Usuario: `{log['author']}`, Canal: `{log['channel']}`, Exitoso: `{log['success']}`"
                    for log in command_logs
                ]
            )

            pages = [
                ""
            ]
            current_page = ""
            for line in description_text.splitlines(keepends=True):
                if len(line) > 4000:
                    if current_page:
                        pages.append(current_page)
                        current_page = ""
                    pages.extend(line[index:index + 4000] for index in range(0, len(line), 4000))
                elif len(current_page) + len(line) > 4000:
                    pages.append(current_page)
                    current_page = line
                else:
                    current_page += line

            if current_page:
                pages.append(current_page)

            pages = pages or [""]
            for page_number, page in enumerate(pages, start=1):
                title = "Registros de comandos del HollowBot"
                if len(pages) > 1:
                    title += f" ({page_number}/{len(pages)})"

                embed = discord.Embed(
                    title=title,
                    description=page,
                    color=discord.Color.purple(),
                )
                await ctx.send(embed=embed)

            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("bot_command_log", ctx.author.name, ctx.channel.name, True)
        except Exception as e:
            print(f"Failed at 'bot_command_log': {e}")
            await log_command_usage("bot_command_log", ctx.author.name, ctx.channel.name, False)

    return tt_info, channel_metrics, bot_metrics, bot_command_log
