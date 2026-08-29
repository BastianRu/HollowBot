from .base import register_common_commands
from .metrics import register_metrics_commands


def register_commands(bot):
    register_common_commands(bot)
    register_metrics_commands(bot)
