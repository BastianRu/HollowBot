import os
import time

import psutil
from discord.ext import tasks

# Basic runtime sampling for the current process, used by the daily bot metrics report.
BOT_START_TIME = time.time()
cpu_samples = []
memory_samples = []
process = psutil.Process(os.getpid())


@tasks.loop(minutes=10.0)
async def monitor_system_usage():
    try:
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_mb = process.memory_info().rss / (1024 * 1024)

        cpu_samples.append(cpu_percent)
        memory_samples.append(memory_mb)
    except Exception as e:
        print(f"Failed at 'monitor_system_usage': {e}")


def get_current_uptime_hours() -> float:
    delta_seconds = time.time() - BOT_START_TIME
    return delta_seconds / 3600


def get_daily_averages(reset: bool = True) -> dict:
    global cpu_samples, memory_samples

    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0.0

    if reset:
        cpu_samples.clear()
        memory_samples.clear()
        print("[Metrics] - Daily averages reset.")

    return {
        "avg_cpu": avg_cpu,
        "avg_memory": avg_memory,
        "uptime_hours": get_current_uptime_hours(),
    }
