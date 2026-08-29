import argparse
import os
import asyncio
from dotenv import load_dotenv
from src.chat_bridge import start_bridge
from src.bot import start_bot
from src.config import CURRENT_VER

# command line args
parser = argparse.ArgumentParser(
    description=f"HollowBot ver. {CURRENT_VER}"
)

# command container (first argument) 
subparsers_principales = parser.add_subparsers(dest="first_arg", required=True)

# cbridge command line
parser_cbridge = subparsers_principales.add_parser("cbridge", help="Chat-bridge commands")
parser_bot = subparsers_principales.add_parser("bot", help="Discord bot commands")

# cbridge sub-container 
subparsers_cbridge = parser_cbridge.add_subparsers(dest="action", required=True)

# bot sub-container
subparsers_bot = parser_bot.add_subparsers(dest="action", required=True)

# cbridge commands
parser_cbridge_start = subparsers_cbridge.add_parser("start", help="Start chat bridge")
#parser_cbridge.add_argument("stop", help="Stop chat bridge") #Not available yet (exit with crtl-c)

# bot commads
parser_bot_start = subparsers_bot.add_parser("start", help="Start discord bot")

args = parser.parse_args()

# Load envs
load_dotenv()

async def main():
    if args.first_arg == "cbridge":
        if args.action == "start":
            print("Starting chat bridge service")
            await start_bridge()
    if args.first_arg == "bot":
        if args.action == "start":
            print("Starting discord bot service")
            await start_bot()
        

asyncio.run(main())