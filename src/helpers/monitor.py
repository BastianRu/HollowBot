import os
import time
from datetime import datetime
import discord
from discord.ext import tasks
import psutil

# Global variables to store metrics
BOT_START_TIME = time.time()  # startup time
cpu_samples = []
memory_samples = []

# Gets the system process for the current bot instance
process = psutil.Process(os.getpid())

# background task to monitor system usage every n minutes
@tasks.loop(minutes=10.0)
async def monitor_system_usage():
    try:
        # cpu usage
        cpu_percent = process.cpu_percent(interval=0.1)
        
        # ram usage in MB
        memory_mb = process.memory_info().rss / (1024 * 1024)
        
        # save samples 
        cpu_samples.append(cpu_percent)
        memory_samples.append(memory_mb)
        
        #print(f"[Metrics] - CPU: {cpu_percent:.2f}%, RAM: {memory_mb:.2f} MB")
    except Exception as e:
        print(f"Failed at 'monitor_system_usage': {e}")


def get_current_uptime_hours() -> float:
    """Returns the current uptime of the bot in hours."""
    delta_seconds = time.time() - BOT_START_TIME
    return delta_seconds / 3600

def get_daily_averages(reset: bool = True) -> dict:
    """Returns the daily averages for CPU and memory usage."""
    global cpu_samples, memory_samples
    
    avg_cpu = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    avg_memory = sum(memory_samples) / len(memory_samples) if memory_samples else 0.0
    
    # clean up the samples for the next day
    if reset:
        cpu_samples.clear()
        memory_samples.clear()
        print("[Metrics] - Daily averages reset.")
    
    return {
        "avg_cpu": avg_cpu,
        "avg_memory": avg_memory,
        "uptime_hours": get_current_uptime_hours()
    }
