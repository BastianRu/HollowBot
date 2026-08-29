from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re


DAY_NAMES = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}


def _safe_zoneinfo(timezone_name: str):
    """Get ZoneInfo object, fallback to UTC on error."""
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def get_next_occurrence_of_day(day_name: str, timezone: str = "America/Bogota") -> str:
    day_name = day_name.lower().strip()
    if day_name not in DAY_NAMES:
        raise ValueError(f"Unknown day name: {day_name}")

    target_weekday = DAY_NAMES[day_name]
    tz = _safe_zoneinfo(timezone)
    today = datetime.now(tz)
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7

    target_date = today + timedelta(days=days_ahead)
    return target_date.strftime("%Y-%m-%d")


def parse_relative_date(date_str: str, timezone: str = "America/Bogota") -> str:
    """Parse relative date string, respecting user timezone.
    
    Supports: "mañana", "proxima_semana", "N_dias", day names (lunes, martes, etc.), or YYYY-MM-DD format.
    """
    date_str = date_str.lower().strip()

    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    tz = _safe_zoneinfo(timezone)
    now_tz = datetime.now(tz)
    
    if date_str in {"mañana", "manana"}:
        return (now_tz + timedelta(days=1)).strftime("%Y-%m-%d")

    if date_str == "proxima_semana":
        return (now_tz + timedelta(days=7)).strftime("%Y-%m-%d")

    dias_match = re.match(r"^(\d+)_dias?$", date_str)
    if dias_match:
        days = int(dias_match.group(1))
        return (now_tz + timedelta(days=days)).strftime("%Y-%m-%d")

    if date_str in DAY_NAMES:
        return get_next_occurrence_of_day(date_str, timezone=timezone)

    raise ValueError(f"Cannot parse date: {date_str}")


def parse_estimated_hours(hours_str: str) -> float:
    raw = hours_str.strip().lower()
    if not raw:
        raise ValueError("Hours cannot be empty")

    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        hours = float(raw)
        if hours <= 0:
            raise ValueError("Hours must be positive")
        return hours

    day_hour_match = re.fullmatch(r"(\d+(?:\.\d+)?)d\s*:\s*(\d+(?:\.\d+)?)h", raw)
    if day_hour_match:
        days = float(day_hour_match.group(1))
        hours_per_day = float(day_hour_match.group(2))
        if days <= 0 or hours_per_day <= 0:
            raise ValueError("Days and hours per day must be positive")
        return days * hours_per_day

    hour_match = re.fullmatch(r"(\d+(?:\.\d+)?)h", raw)
    if hour_match:
        hours = float(hour_match.group(1))
        if hours <= 0:
            raise ValueError("Hours must be positive")
        return hours

    raise ValueError(
        f"Could not parse hours '{hours_str}'. Use a number like '2' or '1.5', or a day format like '15d:2h'."
    )


def parse_task_message(message: str, timezone: str = "America/Bogota"):
    """Parse task message format: [Materia] | [Título] | [Entrega] | [Horas]
    
    Respects user timezone for relative date parsing.
    """
    parts = [part.strip() for part in message.split("|")]

    if len(parts) != 4:
        raise ValueError(
            f"Expected 4 parts separated by '|', got {len(parts)}. Format: [Materia] | [Título] | [Entrega] | [Horas]"
        )

    subject, title, due_date_str, hours_str = parts

    if not subject:
        raise ValueError("Materia (subject) cannot be empty")
    if not title:
        raise ValueError("Título (title) cannot be empty")

    try:
        due_date = parse_relative_date(due_date_str, timezone=timezone)
    except ValueError as exc:
        raise ValueError(f"Error parsing due date: {exc}") from exc

    try:
        estimated_hours = parse_estimated_hours(hours_str)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    return {
        "subject": subject,
        "title": title,
        "due_date": due_date,
        "estimated_hours": estimated_hours,
    }
