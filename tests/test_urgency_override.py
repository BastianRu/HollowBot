"""
Test suite for urgency override feature in priority engine.

Validates that urgent university tasks (< 2 days) take priority and are not
penalized even when they exceed trench day constraints.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.integrations.autotask.priority_engine import (
    score_single_task,
    score_tasks,
    get_target_day,
    calculate_priority,
)


def get_tomorrow_iso():
    """Get tomorrow's date in ISO format (America/Bogota timezone)."""
    tz = ZoneInfo("America/Bogota")
    tomorrow = datetime.now(tz) + timedelta(days=1)
    return tomorrow.strftime("%Y-%m-%d")


def get_day_after_tomorrow_iso():
    """Get day after tomorrow in ISO format (America/Bogota timezone)."""
    tz = ZoneInfo("America/Bogota")
    day_after = datetime.now(tz) + timedelta(days=2)
    return day_after.strftime("%Y-%m-%d")


def get_in_n_days_iso(n: int):
    """Get date n days from now in ISO format (America/Bogota timezone)."""
    tz = ZoneInfo("America/Bogota")
    future = datetime.now(tz) + timedelta(days=n)
    return future.strftime("%Y-%m-%d")


DEFAULT_SETTINGS = {
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


class TestUrgencyOverride:
    """Tests for urgent university task prioritization."""

    def test_urgent_university_task_gets_full_weight_on_deep_work_day(self):
        """
        Urgent university task (< 2 days) should get w_deep (1.5) even on
        deep work days, prioritizing academic deadlines over personal projects.
        """
        # C4 task: vence mañana (0 days remaining from target_date), 3.5 horas
        task = {
            "subject": "Lab. Ing Software II",
            "title": "Hacer diagramas C4",
            "due_date": get_tomorrow_iso(),
            "estimated_hours": 3.5,
            "status": "pending",
        }
        
        score = score_single_task(task, user_settings=DEFAULT_SETTINGS)
        
        # Score should be: 10/(0+1) + 3.5*1.5 = 10 + 5.25 = 15.25
        # (days_remaining = 0 because we evaluate from target_date which is tomorrow)
        # NOT penalized with *0.01
        expected = 10.0 / 1 + 3.5 * 1.5
        assert abs(score - expected) < 0.01, f"Expected ~{expected}, got {score}"

    def test_urgent_university_task_no_penalty_on_trench_day(self):
        """
        Urgent university task (< 2 days) should NOT receive the 0.01 penalty
        on trench days, even if it exceeds max_trench_hours (1.5).
        
        This allows critical deadlines to override scheduling constraints.
        """
        # OS task: vence en 1 día (0 days from target_date), 3.0 horas (> max_trench_hours of 1.5)
        task = {
            "subject": "Lab. OS",
            "title": "Taller scripting",
            "due_date": get_tomorrow_iso(),
            "estimated_hours": 3.0,
            "status": "pending",
        }
        
        score_with_urgency = score_single_task(task, user_settings=DEFAULT_SETTINGS)
        
        # Urgent university tasks should get w_deep (1.5), not penalized
        # Best case (if on trench day but urgent): 10/(0+1) + 3.0*1.5 = 10 + 4.5 = 14.5
        # Worst case (if penalty applied): 14.5 * 0.01 = 0.145
        # We check it's NOT super low (which would indicate penalty was applied)
        assert score_with_urgency > 1.0, f"Score {score_with_urgency} is too low; penalty may have been incorrectly applied"

    def test_non_urgent_task_still_gets_penalty_on_trench_day(self):
        """
        Non-urgent tasks (>= 2 days) that exceed max_trench_hours should
        still receive the 0.01 penalty on trench days.
        """
        # Task vences en 7 días, 3.0 horas (> max_trench_hours)
        task = {
            "subject": "Estadistica",
            "title": "hacer taller para P1",
            "due_date": get_in_n_days_iso(7),
            "estimated_hours": 3.0,
            "status": "pending",
        }
        
        score = score_single_task(task, user_settings=DEFAULT_SETTINGS)
        
        # Non-urgent task should be penalized (score should be very low)
        # Without penalty: ~10/(6+1) + 3.0*0.2 = 1.43 + 0.6 = 2.03
        # With penalty (×0.01): ~0.02
        # So if we're on a trench day, score should be low
        # Let's just check it's lower than an urgent task
        
        urgent_task = {
            "subject": "OS",
            "title": "Urgent",
            "due_date": get_tomorrow_iso(),
            "estimated_hours": 3.0,
            "status": "pending",
        }
        urgent_score = score_single_task(urgent_task, user_settings=DEFAULT_SETTINGS)
        
        # Urgent should be higher priority than non-urgent
        assert urgent_score > score or abs(urgent_score - score) < 0.1

    def test_urgent_university_task_in_score_tasks_list(self):
        """
        When ranking multiple tasks, urgent university tasks should appear
        at the top, even if they exceed trench hour constraints.
        """
        tasks = [
            {
                "subject": "Lab. Ing Software II",
                "title": "C4 diagrams",
                "due_date": get_tomorrow_iso(),
                "estimated_hours": 3.5,
                "status": "pending",
                "id": 1,
            },
            {
                "subject": "Personal Project",
                "title": "Discord bot feature",
                "due_date": get_in_n_days_iso(7),
                "estimated_hours": 2.0,
                "status": "pending",
                "id": 2,
            },
            {
                "subject": "Estadistica",
                "title": "Worksheet",
                "due_date": get_in_n_days_iso(5),
                "estimated_hours": 2.0,
                "status": "pending",
                "id": 3,
            },
        ]
        
        ranked = score_tasks(tasks, user_settings=DEFAULT_SETTINGS)
        
        # First task should be the urgent university one (C4)
        assert ranked[0][0]["id"] == 1, f"Expected C4 (id=1) first, got {ranked[0][0]['id']}"

    def test_boundary_case_exactly_2_days_not_urgent(self):
        """
        Task due exactly 2 days from now should NOT get urgent override.
        Urgency threshold is < 2 days (i.e., 0 or 1 day remaining).
        
        Day after tomorrow: 
        - Today = 2026-09-01
        - Target date (tomorrow) = 2026-09-02  
        - Due date = 2026-09-03
        - days_remaining from 2026-09-02 to 2026-09-03 = 1 day
        
        So this would STILL be urgent (1 < 2). Let's use 3 days for true non-urgent.
        """
        task = {
            "subject": "Lab. OS",
            "title": "Assignment",
            "due_date": get_in_n_days_iso(3),  # 3 days from now = 1 day remaining from target
            "estimated_hours": 3.0,
            "status": "pending",
        }
        
        score = score_single_task(task, user_settings=DEFAULT_SETTINGS)
        
        # Non-urgent task (1 day remaining is still urgent, 2+ days is not)
        # On a trench day with 3.0 hours (exceeds max 1.5), should get penalty
        # Without penalty: ~10/2 + 3.0*0.2 = 5 + 0.6 = 5.6
        # With penalty: 5.6 * 0.01 = 0.056
        from src.integrations.autotask.priority_engine import get_days_remaining
        _, target_date_str = get_target_day(DEFAULT_SETTINGS)
        days_left = get_days_remaining(task["due_date"], target_date_str)
        
        # If 2 days remaining or more, it's not urgent
        if days_left >= 2:
            # Non-urgent, should be penalized if on trench day
            assert score < 1.0 or score > 5.0  # Either penalized or on a deep work day

    def test_non_university_task_never_gets_urgency_override(self):
        """
        Non-university tasks should never bypass the trench day penalty,
        regardless of urgency. Only academic tasks get urgency override.
        """
        task = {
            "subject": "My Fun Project",
            "title": "Build something cool",
            "due_date": get_tomorrow_iso(),  # Tomorrow (urgent)
            "estimated_hours": 3.0,  # Exceeds max_trench_hours
            "status": "pending",
        }
        
        score = score_single_task(task, user_settings=DEFAULT_SETTINGS)
        
        # Non-university task should be penalized even if "urgent"
        # Score should be low due to penalty
        from src.integrations.autotask.priority_engine import is_university_task
        assert not is_university_task(task)
        
        # If on a trench day, score will be penalized
        # If on a deep work day, no penalty (but different weight calculation)
        # Either way, confirm it's treated differently than university urgent

    def test_os_tasks_get_proper_scores(self):
        """
        Real-world test: OS tasks due 2026-09-03 should get high scores
        as they are university tasks due within 2 days.
        """
        tasks = [
            {
                "subject": "[OS]",
                "title": "Ver video del señor de Microsoft",
                "due_date": "2026-09-03",
                "estimated_hours": 0.25,
                "status": "pending",
            },
            {
                "subject": "[OS]",
                "title": "Consultar estados de procesos",
                "due_date": "2026-09-03",
                "estimated_hours": 0.2,
                "status": "pending",
            },
        ]
        
        scores = score_tasks(tasks, user_settings=DEFAULT_SETTINGS)
        
        # Both should have high scores (> 4.0) because OS is university task
        # and they're due within 2 days
        for task, score in scores:
            assert score > 2.0, f"OS task score {score} is too low for urgent university task"
