from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent
from TikTokLive import TikTokLiveClient
from dotenv import load_dotenv
import discord
import asyncio
import aiohttp
import pprint
import os

# Load envs
load_dotenv()
TIKTOK_USERNAME = os.getenv("TIKTOK_USERNAME")
# discord channel webhook
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# create TikTokLive client
tt_client = TikTokLiveClient(unique_id=TIKTOK_USERNAME)

async def send_to_discord_webhook(username: str, avatar_url: str, message: str):
    """sends a message to discord through channel webhook."""
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(WEBHOOK_URL, session=session)
    
        await webhook.send(
            content=message,
            username=f"{username}",
            avatar_url=avatar_url if avatar_url else None
        )

# TIKTOK LIVE EVENTS
@tt_client.on(ConnectEvent)
async def on_tt_connect(event: ConnectEvent):
    print(f"On live! streaming {TIKTOK_USERNAME} chat")


@tt_client.on(DisconnectEvent)
async def on_tt_disconnect(event: DisconnectEvent):
    print("Live has ended.")

async def main():
    # loop for tiktok (this is required by TikTokLive API)
    while True:
        try:
            print(f"fetching {TIKTOK_USERNAME} status")
            await tt_client.start(fetch_room_info=True, fetch_gift_info=False)

            #if tt_client.room_info:
            #  pprint.pprint(tt_client.room_info)

            #if tt_client.gift_info:
            #  print(tt_client.gift_info)
            

        except Exception as e:
            # if live offline, tries to restart 
            print(f"Stream offline or lost, retry in 30s ({e})")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())