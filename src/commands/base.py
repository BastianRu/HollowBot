import discord

from src.config import CURRENT_VER, TIKTOK_USERNAME
from src.infrastructure.database import log_command_usage, update_daily_bot_metrics


def register_common_commands(bot):
    # These are the lightweight global commands that are available at startup.
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
            await update_daily_bot_metrics(discord_commands_increment=1)
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

            command_list = "".join([f"- `{cmd.name}`: {cmd.brief if cmd.brief else 'Sin descripcion'} \n" if cmd.name != 'help' else '' for cmd in bot.commands])

            description_text = (
                f"Fecha de inicio del desarrollo: `17 de Agosto de 2026` \n"
                f"ID de la aplicacion: `{app_info.id}`\n"
                f"Nombre de la app: `{app_info.name}`\n"
                f"Prefijo de comando actual: `{bot.command_prefix}` \n\n"
                f"Lista de comandos: \n {command_list}"
                f"- `help`: Muestra la lista de comandos y sus descripciones. \n"

            )

            embed = discord.Embed(
                title=f"HollowBot v{CURRENT_VER}",
                description=description_text,
                color=discord.Color.purple(),
            )

            await ctx.send(embed=embed)
            await update_daily_bot_metrics(discord_commands_increment=1)
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

                    2. Estado: el texto que se va a mostrar debajo del nombre del bot.
                """
    )
    async def change_status(ctx, state: str, text: str = ""):
        status_map = {
            "playing": discord.ActivityType.playing,
            "jugar": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "ver": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "escuchar": discord.ActivityType.listening,
            "competing": discord.ActivityType.competing,
            "competir": discord.ActivityType.competing,
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
                    activity=discord.Activity(type=status_map[state_key], name=text),
                )

            embed = discord.Embed(
                title="Estado y actividad actualizados:",
                description=f"Actividad: `{state}` \n Estado: `{text}`",
                color=discord.Color.purple(),
            )
            await ctx.send(embed=embed)

            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("change_status", ctx.author.name, ctx.channel.name, True)
        except Exception as e:
            print(f"Failed at 'change_status': {e}")
            await log_command_usage("change_status", ctx.author.name, ctx.channel.name, False)

    @bot.command(brief="Limpia los mensajes del canal actual (100 por defecto)")
    async def clean_channel(ctx, limit: int = 100):
        try:
            async with ctx.typing():
                deleted = await ctx.channel.purge(limit=limit)
                await ctx.send(f"✅ Se eliminaron {len(deleted)} mensajes del canal (por defecto 100)")
            await update_daily_bot_metrics(discord_commands_increment=1)
            await log_command_usage("clean_channel", ctx.author.name, ctx.channel.name, True)
        except Exception as e:
            print(f"Failed at 'clean_channel': {e}")
            await ctx.send("❌ Ocurrió un error al limpiar el canal. (Los mensajes anteriores a 14 dias no pueden ser eliminados por el bot)")
            await log_command_usage("clean_channel", ctx.author.name, ctx.channel.name, False)

    return ping, info, change_status, clean_channel
