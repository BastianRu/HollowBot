from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent
from TikTokLive import TikTokLiveClient
from dotenv import load_dotenv
import discord
import asyncio
import aiohttp
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
            username=f"{username} (TikTok)",
            avatar_url=avatar_url if avatar_url else None
        )

# TIKTOK LIVE EVENTS
@tt_client.on(ConnectEvent)
async def on_tt_connect(event: ConnectEvent):
    print(f"On live! streaming {TIKTOK_USERNAME} chat")


@tt_client.on(DisconnectEvent)
async def on_tt_disconnect(event: DisconnectEvent):
    print("Live has ended.")

@tt_client.on(CommentEvent)
async def on_tt_comment(event: CommentEvent):
    user = event.user
    nickname = getattr(user, "nickname", None) or getattr(user, "unique_id", "Usuario TikTok")
    
    avatar_url = ""
    
    for attr in ["avatar_thumb", "avatar_medium", "avatar_large"]:
        if hasattr(user, attr):
            img_obj = getattr(user, attr)
            
            # this is a very aggresive way to look for the avatar urls
            # remember me look for the exact atribute name later
            for list_attr in ["url_list", "urls_list", "url", "urls"]:
                if hasattr(img_obj, list_attr):
                    urls = getattr(img_obj, list_attr)
                    if isinstance(urls, (list, tuple)) and len(urls) > 0:
                        avatar_url = urls[0]
                        break
                    elif isinstance(urls, str) and urls.startswith("http"):
                        avatar_url = urls
                        break
            if avatar_url:
                break

    #print(f"[TikTok] {nickname}: {event.comment}")

    # send webhook to discord
    try:
        await send_to_discord_webhook(
            username=nickname,
            avatar_url=avatar_url,
            message=event.comment
        )
        return 0
    except Exception as e:
        print(f"faild to send discord webhook: {e}")

async def start_bridge():
    # loop for tiktok (this is required by TikTokLive API)
    while True:
        try:
            print(f"fetching {TIKTOK_USERNAME} status")
            await tt_client.start()
        except Exception as e:
            # if live offline, tries to restart 
            print(f"Stream offline or lost, retry in 30s ({e})")
            await asyncio.sleep(30)
           