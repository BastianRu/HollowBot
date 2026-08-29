import logging

from src.infrastructure.repositories.autotask_repository import (
    create_task,
    get_pending_tasks,
    get_user_settings,
    save_user_settings,
    update_task_status,
    update_user_setting,
)
from src.integrations.autotask.parser import parse_task_message
from src.integrations.autotask.priority_engine import (
    break_down_task,
    get_top_n_tasks,
    score_single_task,
    score_tasks,
    should_break_down_task,
)

logger = logging.getLogger(__name__)


def get_default_user_settings():
    return {
        "timezone": "America/Bogota",
        "trench_days": [0, 2, 4],
        "deep_work_days": [1, 3],
        "w_trench": 0.2,
        "w_deep": 1.5,
        "w_weekend_default": 1.0,
        "max_trench_hours": 1.5,
        "block_size": 2.0,
        "weekend_mode": "HARD_WORK_BALANCED",
    }


def load_user_settings(user_id):
    return get_user_settings(str(user_id))

def _build_task_response(task_input, user_id):
    user_settings = load_user_settings(user_id)
    #print(f"User settings for user {user_id}: {user_settings}")
    
    # Check if task is assignable on trench days (Bug #10 fix: validate feasibility)
    from src.integrations.autotask.priority_engine import get_target_day, is_feasible_for_trenches
    target_day_weekday, _ = get_target_day(user_settings)
    is_trench_day = target_day_weekday in set(user_settings.get("trench_days", [0, 2, 4]))
    
    # If task is too long for a trench day, warn and auto-break it down
    if is_trench_day and not is_feasible_for_trenches(task_input["estimated_hours"], user_settings):
        # Auto-break down task if on trench day and exceeds max_trench_hours
        should_break_down = True
    else:
        should_break_down = should_break_down_task(task_input["estimated_hours"], user_settings)
    
    if should_break_down:
        blocks = break_down_task(task_input["estimated_hours"], user_settings)
        parent_task_id = None
        for index, (block_label, hours) in enumerate(blocks, 1):
            block_title = f"{block_label} {task_input['title']}"
            task_id = create_task(
                title=block_title,
                subject=task_input["subject"],
                due_date=task_input["due_date"],
                estimated_hours=hours,
                user_id=user_id,
                is_subtask=(index > 1),
                block_number=index,
                total_blocks=len(blocks),
                parent_id=parent_task_id if index > 1 else None,
            )
            if index == 1:
                parent_task_id = task_id

        response = "✅ Tarea dividida en {} bloques:\n".format(len(blocks))
        if is_trench_day and task_input["estimated_hours"] > user_settings.get("max_trench_hours", 1.5):
            response += f"⚠️ Nota: Como hoy es un día trinchera y la tarea excede {user_settings.get('max_trench_hours', 1.5)}h, fue desglosada automáticamente.\n\n"
        for block_label, hours in blocks:
            response += f"  • {block_label} - {hours}h\n"
        return response

    task_id = create_task(
        title=task_input["title"],
        subject=task_input["subject"],
        due_date=task_input["due_date"],
        estimated_hours=task_input["estimated_hours"],
        user_id=user_id,
    )
    score = score_single_task(task_input, user_settings=user_settings)
    return (
        f"✅ Tarea creada (ID: {task_id})\n"
        f"📌 Materia: {task_input['subject']}\n"
        f"📝 Título: {task_input['title']}\n"
        f"📅 Entrega: {task_input['due_date']}\n"
        f"⏰ Horas: {task_input['estimated_hours']}\n"
        f"🎯 Prioridad: {score:.2f}"
    )


def _format_settings_value(key, value):
    if key in {"trench_days", "deep_work_days"}:
        return ",".join(str(item) for item in value)
    return str(value)


def _should_inject_deep_work_placeholder(user_settings: dict, all_tasks: list) -> bool:
    """Check if we should inject a Deep Work placeholder in top 3.
    
    Conditions:
    - Tomorrow is a Deep Work day
    - No urgent university tasks (< 7 days deadline)
    """
    from src.integrations.autotask.priority_engine import get_target_day, has_pending_university_tasks
    
    target_day_weekday, _ = get_target_day(user_settings)
    deep_work_days = set(user_settings.get("deep_work_days", [1, 3]))
    
    # Check if tomorrow is a deep work day
    if target_day_weekday not in deep_work_days:
        return False
    
    # Check if there are urgent university tasks
    has_urgent_university = has_pending_university_tasks(all_tasks, user_settings=user_settings)
    
    return not has_urgent_university


def _detect_critical_overload(scored_tasks: list) -> list:
    """Detect tasks #4-5 that are critical (due today or earlier).
    
    Returns list of (task, score, days_left) tuples for tasks that are critical
    and didn't make the top 3.
    
    Bug #9 fix: Implement CRUNCH alert logic.
    """
    from src.integrations.autotask.priority_engine import get_days_remaining
    
    critical_tasks = []
    
    # Check tasks #4-5 for critical status
    for i in range(3, min(5, len(scored_tasks))):
        task, score = scored_tasks[i]
        days_left = get_days_remaining(task["due_date"])
        
        # Critical threshold: due today or earlier (0 days remaining)
        if days_left <= 0:
            critical_tasks.append((task, score, days_left))
    
    return critical_tasks


def register_autotask_commands(bot):
    @bot.group(name="autotask")
    async def autotask_group(ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "Uso: `hw autotask setup ...` | `hw autotask config` | `hw autotask add_task ...` | `hw autotask tasks` | `hw autotask top3` | `hw autotask complete 1`"
            )

    @autotask_group.command(name="setup")
    async def setup_autotask(ctx, *, payload: str = None):
        user_id = str(ctx.author.id)
        if not payload:
            await ctx.send(
                "**Configuración de AutoTask**\n"
                "Uso: `hw autotask setup timezone America/Bogota trench_days 0,2,4 deep_work_days 1,3 block_size 2 max_trench_hours 1.5 w_trench 0.2 w_deep 1.5 weekend_mode STRICT_UNIVERSITY`"
            )
            return

        parts = payload.split()
        if len(parts) % 2 != 0:
            await ctx.send("❌ El formato de setup debe ser `clave valor` por cada parámetro.")
            return

        settings = {}
        for idx in range(0, len(parts), 2):
            key = parts[idx].strip().lower()
            value = parts[idx + 1].strip()
            settings[key] = value

        try:
            success = save_user_settings(user_id, **settings)
        except Exception:
            logger.exception("Failed to save setup settings for user=%s", user_id)
            success = False

        if not success:
            await ctx.send("❌ Uno o más parámetros no son válidos. Revisa la sintaxis o los rangos permitidos.")
            return

        active_settings = get_user_settings(user_id)
        response = "✅ Configuración guardada:\n"
        for key, value in active_settings.items():
            response += f"• {key}: {_format_settings_value(key, value)}\n"
        await ctx.send(response)

    @autotask_group.command(name="config")
    async def config_autotask(ctx, key: str = None, value: str = None):
        user_id = str(ctx.author.id)
        if key is None and value is None:
            settings = get_user_settings(user_id)
            response = "**⚙️ Configuración actual de AutoTask**\n"
            for setting_name, setting_value in settings.items():
                response += f"• {setting_name}: {_format_settings_value(setting_name, setting_value)}\n"
            await ctx.send(response)
            return

        if key is None or value is None:
            await ctx.send("Uso: `hw autotask config <clave> <valor>` o `hw autotask config` para ver toda la configuración.")
            return

        if not update_user_setting(user_id, key.lower(), value):
            await ctx.send(f"❌ El parámetro `{key}` no es válido o el valor no cumple los rangos permitidos.")
            return

        updated_value = get_user_settings(user_id).get(key.lower())
        await ctx.send(
            f"✅ Parámetro actualizado: `{key}` = {_format_settings_value(key.lower(), updated_value)}"
        )

    @autotask_group.command(name="add_task")
    async def add_task_command(ctx, *, task_text: str):
        async with ctx.typing():
            try:
                user_settings = load_user_settings(str(ctx.author.id))
                user_timezone = user_settings.get("timezone", "America/Bogota")
                # Pass timezone to parser for proper date handling (Bug #6 fix)
                task_input = parse_task_message(task_text, timezone=user_timezone)
                response = _build_task_response(task_input, str(ctx.author.id))
                print(f"Task added for user {ctx.author.id}: {task_input}")
                await ctx.send(response)
            except ValueError as exc:
                await ctx.send(
                    f"❌ Error parseando tarea:\n{exc}\n\n"
                    "**Formato esperado:**\n"
                    "`hw autotask add_task [Materia] | [Título] | [Entrega] | [Horas]`\n\n"
                    "**Ejemplo:**\n"
                    "`hw autotask add_task OS | Ver documental | mañana | 2`"
                )
            except Exception as exc:  # pragma: no cover - defensive guard for runtime DB issues
                logger.exception("Unhandled AutoTask add_task failure for user=%s", ctx.author.id)
                await ctx.send(
                    "❌ Ocurrió un error al procesar la tarea. Intenta de nuevo o usa `hw autotask repair` si la base de datos quedó corrupta."
                )

    @autotask_group.command(name="tasks")
    async def list_tasks(ctx):
        async with ctx.typing():
            try:
                all_tasks = get_pending_tasks(str(ctx.author.id))
                if not all_tasks:
                    await ctx.send("No hay tareas pendientes.")
                    return

                user_settings = get_user_settings(str(ctx.author.id))
                scored_tasks = score_tasks(all_tasks, user_settings=user_settings)

                response = "**📋 Tareas pendientes (ordenadas por prioridad):**\n\n"
                for i, (task, score) in enumerate(scored_tasks, 1):
                    response += (
                        f"{i}. [{task['subject']}] {task['title']}\n"
                        f"   • Vence: {task['due_date']}\n"
                        f"   • Horas: {task['estimated_hours']}\n"
                        f"   • Score: {score:.2f}\n\n"
                    )

                await ctx.send(response)
            except Exception:
                logger.exception("Unhandled AutoTask tasks failure for user=%s", ctx.author.id)
                await ctx.send("❌ No pude cargar tus tareas. Reintenta en unos segundos.")

    @autotask_group.command(name="top3")
    async def show_top3(ctx):
        async with ctx.typing():
            try:
                all_tasks = get_pending_tasks(str(ctx.author.id))
                if not all_tasks:
                    await ctx.send("No hay tareas pendientes.")
                    return

                user_settings = load_user_settings(str(ctx.author.id))
                top_tasks = get_top_n_tasks(all_tasks, n=3, user_settings=user_settings)
                
                # Bug #9 fix: Detect critical overload (tasks due today not in top 3)
                all_scored_tasks = score_tasks(all_tasks, user_settings=user_settings)
                critical_tasks = _detect_critical_overload(all_scored_tasks)

                response = "**🚀 Top 3 tareas por prioridad:**\n\n"
                for i, (task, score) in enumerate(top_tasks, 1):
                    response += (
                        f"{i}. [{task['subject']}] {task['title']}\n"
                        f"   • Vence: {task['due_date']}\n"
                        f"   • Horas: {task['estimated_hours']}\n"
                        f"   • Prioridad: {score:.2f}\n\n"
                    )
                
                # Bug #4, #12 fix: Inject Deep Work placeholder if applicable
                if _should_inject_deep_work_placeholder(user_settings, all_tasks):
                    response += (
                        "4. [Deep Work Personal] Bloque de Enfoque Libre\n"
                        "   • Descripción: Bloque sugerido para trabajo de alta concentración\n"
                        "   • Duración: 2-3 horas (configurable)\n"
                        "   • Notas: Para proyectos personales (ML, Bot, Coursera, etc.)\n\n"
                    )
                
                # Bug #9 fix: Add CRUNCH alert if critical tasks exist
                if critical_tasks:
                    response += (
                        "---\n\n"
                        "⚠️ **ALERTA DE CRUNCH: Tareas críticas excedentes**\n\n"
                        "Las siguientes tareas están VENCIDAS o VENCEN HOY y no entraron en el Top 3:\n\n"
                    )
                    for task, score, days_left in critical_tasks:
                        status = "VENCIDA" if days_left < 0 else "VENCE HOY"
                        response += (
                            f"• [{task['subject']}] {task['title']} - {status}\n"
                            f"  - Horas: {task['estimated_hours']} | Score: {score:.2f}\n"
                        )
                    response += (
                        "\n💡 **Recomendación:** Considera agregar estas al sprint actual o "
                        "solicitar extensiones de plazo.\n"
                    )

                await ctx.send(response)
            except Exception:
                logger.exception("Unhandled AutoTask top3 failure for user=%s", ctx.author.id)
                await ctx.send("❌ No pude calcular el ranking. Reintenta en unos segundos.")

    @autotask_group.command(name="complete")
    async def complete_task(ctx, position: int):
        async with ctx.typing():
            try:
                all_tasks = get_pending_tasks(str(ctx.author.id))
                if not all_tasks:
                    await ctx.send("❌ No hay tareas pendientes para completar.")
                    return

                user_settings = get_user_settings(str(ctx.author.id))
                scored_tasks = score_tasks(all_tasks, user_settings=user_settings)

                if position < 1 or position > len(scored_tasks):
                    await ctx.send(f"❌ Posición {position} fuera de rango. Usa un número entre 1 y {len(scored_tasks)}.")
                    return

                task, _ = scored_tasks[position - 1]
                success = update_task_status(task["id"], "completed")

                if success:
                    await ctx.send(f"✅ Completada: [{task['subject']}] {task['title']}")
                else:
                    await ctx.send(f"❌ No se pudo completar la posición {position}.")
            except Exception:
                logger.exception("Unhandled AutoTask complete failure for user=%s", ctx.author.id)
                await ctx.send("❌ No pude completar la tarea. Reintenta en unos segundos.")

    return autotask_group
