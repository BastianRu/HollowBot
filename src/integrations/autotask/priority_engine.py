import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_USER_SETTINGS = {
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

UNIVERSITY_KEYWORDS = {
    "universidad",
    "universitario",
    "ing",
    "ingenieria",
    "software",
    "estructuras",
    "algebra",
    "calculo",
    "fisica",
    "programacion",
    "bases",
    "bd",
    "matematicas",
    "ciencias",
    "carrera",
    "materia",
    "curso",
    "os",
    "lab. os",
    "ing. software",
    "estadistica",
}


def is_university_task(task: dict) -> bool:
    if not isinstance(task, dict):
        return False

    if task.get("is_university") is not None:
        return bool(task.get("is_university"))

    subject = str(task.get("subject", "")).lower()
    if not subject:
        return False

    return any(keyword in subject for keyword in UNIVERSITY_KEYWORDS)


def _safe_zoneinfo(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def get_days_remaining(due_date: str, evaluation_date: str = None, timezone: str = "America/Bogota") -> int:
    if evaluation_date is None:
        tz = _safe_zoneinfo(timezone)
        evaluation_date = datetime.now(tz).strftime("%Y-%m-%d")

    due = datetime.strptime(due_date, "%Y-%m-%d")
    eval_dt = datetime.strptime(evaluation_date, "%Y-%m-%d")
    return (due - eval_dt).days


def get_target_day(user_settings: dict = None):
    """Get the target day for task execution (tomorrow or next business day).
    
    If tomorrow is a weekend and weekend_mode is FULL_REST, returns next Monday.
    Handles timezone correctly according to user settings.
    """
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    tz_name = settings.get("timezone", "America/Bogota")
    tz = _safe_zoneinfo(tz_name)
    weekend_mode = str(settings.get("weekend_mode", "HARD_WORK_BALANCED")).upper()
    
    tomorrow = datetime.now(tz) + timedelta(days=1)
    target_weekday = tomorrow.weekday()
    
    # If tomorrow is a weekend and mode is FULL_REST, advance to next Monday
    if target_weekday in {5, 6} and weekend_mode == "FULL_REST":
        days_to_monday = (7 - target_weekday) % 7 or 7  # Skip to Monday
        target_date = datetime.now(tz) + timedelta(days=1 + days_to_monday)
        target_weekday = target_date.weekday()
        return target_weekday, target_date.strftime("%Y-%m-%d")
    
    return target_weekday, tomorrow.strftime("%Y-%m-%d")


def get_effort_weight(target_day_weekday: int, task: dict = None, weekend_university_pending: bool = False, user_settings: dict = None, days_remaining: int = None) -> float:
    """Calculate effort weight for a given day.
    
    Respects weekend modes:
    - FULL_REST: W=0 (no tasks on weekends)
    - STRICT_UNIVERSITY: W=1.2 for university tasks, W=0.2 otherwise
    - HARD_WORK_BALANCED: W=1.2 if university pending, W=1.5 otherwise (personal projects)
    
    Deep work days get high weight (1.5), trench days get low weight (0.2).
    
    URGENCY OVERRIDE: University tasks due within 2 days take priority and use full
    deep work weight (1.5) even if it displaces personal projects, as academic deadlines
    are critical and non-negotiable.
    """
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    trench_days = set(settings.get("trench_days", [0, 2, 4]))
    deep_work_days = set(settings.get("deep_work_days", [1, 3]))
    weekend_days = {5, 6}
    w_trench = float(settings.get("w_trench", 0.2))
    w_deep = float(settings.get("w_deep", 1.5))
    w_weekend_default = float(settings.get("w_weekend_default", 1.0))
    weekend_mode = str(settings.get("weekend_mode", "HARD_WORK_BALANCED")).upper()

    # URGENCY OVERRIDE: University tasks due within 2 days get full deep work weight
    # This prioritizes critical academic deadlines over personal projects
    if (task and 
        is_university_task(task) and 
        days_remaining is not None and 
        days_remaining < 2):
        return w_deep
    
    # Deep work days have highest priority (for personal projects when no urgent university tasks)
    if target_day_weekday in deep_work_days:
        return w_deep
    
    # Trench days have lowest weight (quick tasks only)
    if target_day_weekday in trench_days:
        return w_trench
    
    # Weekend handling
    if target_day_weekday in weekend_days:
        if weekend_mode == "FULL_REST":
            return 0.0
        
        if weekend_mode == "HARD_WORK_BALANCED":
            # Auto-switch: if university tasks pending, clear university (W=1.2)
            # Otherwise, switch to personal projects (W=1.5)
            if weekend_university_pending:
                return 1.2  # UNIVERSITY_CLEARANCE
            else:
                return 1.5  # HARD_WORK_PERSONAL - free top 3 for personal projects
        
        if weekend_mode == "STRICT_UNIVERSITY":
            if task and is_university_task(task):
                return 1.2
            return 0.2
        
        # Default fallback for weekend
        return w_weekend_default
    
    # Fallback (should not reach here if settings are valid)
    return w_weekend_default


def calculate_priority(due_date: str, estimated_hours: float, target_day_weekday: int = None, evaluation_date: str = None, task: dict = None, weekend_university_pending: bool = False, user_settings: dict = None) -> float:
    """Calculate task priority using the formula: P = (10 / (dias_restantes + 1)) + (estimated_hours * W).
    
    dias_restantes is calculated from target_date (tomorrow/next business day), not today.
    This ensures priority reflects when task will actually be executed.
    """
    if target_day_weekday is None:
        target_day_weekday, target_date_str = get_target_day(user_settings)
    else:
        _, target_date_str = get_target_day(user_settings)

    # CRITICAL: Calculate days_remaining from target_date (when task will execute), not from today
    days_remaining = get_days_remaining(
        due_date,
        evaluation_date=target_date_str,  # Use target_date instead of today
        timezone=(user_settings or DEFAULT_USER_SETTINGS or {}).get("timezone", "America/Bogota"),
    )
    
    weight = get_effort_weight(
        target_day_weekday,
        task=task,
        weekend_university_pending=weekend_university_pending,
        user_settings=user_settings,
        days_remaining=days_remaining,
    )

    days_factor = max(days_remaining, 0)
    return (10.0 / (days_factor + 1)) + (estimated_hours * weight)


def should_break_down_task(estimated_hours: float, user_settings: dict = None) -> bool:
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    block_size = float(settings.get("block_size", 2.0))
    return estimated_hours > block_size * 2


def break_down_task(estimated_hours: float, user_settings: dict = None):
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    block_size = float(settings.get("block_size", 2.0))

    if estimated_hours <= block_size * 2:
        return [("[Bloque 1/1]", estimated_hours)]

    num_blocks = math.ceil(estimated_hours / block_size)
    blocks = []
    for i in range(num_blocks):
        hours_in_block = min(block_size, estimated_hours - (i * block_size))
        block_label = f"[Bloque {i + 1}/{num_blocks}]"
        blocks.append((block_label, hours_in_block))
    return blocks


def is_feasible_for_trenches(estimated_hours: float, user_settings: dict = None) -> bool:
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    max_trench_hours = float(settings.get("max_trench_hours", 1.5))
    return estimated_hours <= max_trench_hours


def has_pending_university_tasks(tasks: list, evaluation_date: str = None, user_settings: dict = None) -> bool:
    """Check if there are university tasks pending within 7 days.
    
    Respects user timezone for date calculations.
    """
    if evaluation_date is None:
        settings = user_settings or DEFAULT_USER_SETTINGS or {}
        tz_name = settings.get("timezone", "America/Bogota")
        tz = _safe_zoneinfo(tz_name)
        evaluation_date = datetime.now(tz).strftime("%Y-%m-%d")

    for task in tasks:
        if task.get("status") != "pending":
            continue
        if not is_university_task(task):
            continue

        days_left = get_days_remaining(
            task["due_date"],
            evaluation_date,
            timezone=(user_settings or DEFAULT_USER_SETTINGS or {}).get("timezone", "America/Bogota")
        )
        if 0 <= days_left <= 7:
            return True

    return False


def score_single_task(task: dict, evaluation_date: str = None, user_settings: dict = None):
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    target_day_weekday, target_date_str = get_target_day(settings)
    weekend_university_pending = has_pending_university_tasks([task], evaluation_date, user_settings=settings)
    score = calculate_priority(
        task["due_date"],
        task["estimated_hours"],
        target_day_weekday,
        evaluation_date,
        task=task,
        weekend_university_pending=weekend_university_pending,
        user_settings=settings,
    )

    # Only penalize non-feasible trench tasks if they are NOT urgent university tasks
    if target_day_weekday in set(settings.get("trench_days", [0, 2, 4])):
        if not is_feasible_for_trenches(task["estimated_hours"], settings):
            # Check if task is urgent university task (< 2 days)
            days_remaining = get_days_remaining(
                task["due_date"],
                evaluation_date=target_date_str,
                timezone=settings.get("timezone", "America/Bogota"),
            )
            is_urgent_university = (is_university_task(task) and days_remaining < 2)
            
            # Only apply penalty if NOT urgent university task
            # Urgent academic deadlines override trench day constraints
            if not is_urgent_university:
                score *= 0.01

    return score


def score_tasks(tasks: list, evaluation_date: str = None, user_settings: dict = None):
    """Score all tasks and return sorted list.
    
    Tiebreaker order:
    1. Priority score (descending)
    2. Due date (ascending - closer deadline first)
    3. Estimated hours (ascending - shorter tasks first)
    4. Task ID (ascending - stable sort for identical tasks)
    """
    settings = user_settings or DEFAULT_USER_SETTINGS or {}
    target_day_weekday, _ = get_target_day(settings)
    weekend_university_pending = has_pending_university_tasks(tasks, evaluation_date, user_settings=settings)
    trench_days = set(settings.get("trench_days", [0, 2, 4]))
    scored_tasks = []

    for task in tasks:
        if task.get("status") == "completed":
            continue

        score = calculate_priority(
            task["due_date"],
            task["estimated_hours"],
            target_day_weekday,
            evaluation_date,
            task=task,
            weekend_university_pending=weekend_university_pending,
            user_settings=settings,
        )

        # Only penalize non-feasible trench tasks if they are NOT urgent university tasks
        if target_day_weekday in trench_days:
            if not is_feasible_for_trenches(task["estimated_hours"], settings):
                # Check if task is urgent university task (< 2 days)
                _, target_date_str = get_target_day(settings)
                days_remaining = get_days_remaining(
                    task["due_date"],
                    evaluation_date=target_date_str,
                    timezone=settings.get("timezone", "America/Bogota"),
                )
                is_urgent_university = (is_university_task(task) and days_remaining < 2)
                
                # Only apply penalty if NOT urgent university task
                # Urgent academic deadlines override trench day constraints
                if not is_urgent_university:
                    score *= 0.01

        scored_tasks.append((task, score))

    scored_tasks.sort(
        key=lambda x: (
            -x[1],                           # Score (descending)
            x[0]["due_date"],               # Due date (ascending - earlier first)
            x[0]["estimated_hours"],        # Hours (ascending - shorter first)
            x[0].get("id", 0),              # Task ID (ascending - stable sort)
        )
    )
    return scored_tasks


def get_top_n_tasks(tasks: list, n: int = 3, evaluation_date: str = None, user_settings: dict = None):
    scored = score_tasks(tasks, evaluation_date, user_settings=user_settings)
    return scored[:n]
