import json
import time
import httpx
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv() 

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "NO_KEY_FOUND")
RAPIDAPI_HOST = "tiktok-api23.p.rapidapi.com"

CACHE_FILE = Path("src/data/tiktok_cache.json")
CACHE_TTL = 8 * 60 * 60  # 8 hours in seconds

def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_cache(cache_data: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Warn] could not save cache:: {e}")

async def get_user_profile_info_rapidapi(username: str, force_refresh: bool = False) -> dict | None:
    clean_username = username.lstrip("@").lower()
    now = time.time()
    
    _profile_cache = _load_cache()

    # 1. Comprobar Caché Local (6 horas)
    if clean_username in _profile_cache:
        cached_item = _profile_cache[clean_username]
        data = cached_item.get("data")
        timestamp = cached_item.get("timestamp", 0)

        if now - timestamp < CACHE_TTL and not force_refresh:
            remaining_min = int((CACHE_TTL - (now - timestamp)) / 60)
            print(f"[Cache] fetching @{clean_username} ({remaining_min} min remaining)")
            return data

    print(f"[RapidAPI] fetching @{clean_username}...")
    url = f"https://{RAPIDAPI_HOST}/api/user/info"
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    
    params = {"uniqueId": clean_username}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                print(f"[RapidAPI Error {response.status_code}] HTTP request failed")
                return _profile_cache.get(clean_username, {}).get("data")

            data = response.json()
            user_info = data.get("userInfo", {})
            user = user_info.get("user", {})
            stats = user_info.get("stats", {})

            if not user:
                print(f"[Warn] @{clean_username} not found or empty.")
                return _profile_cache.get(clean_username, {}).get("data")

            result = {
                "sec_uid": user.get("secUid", ""),            # unmutable ID
                "username": user.get("uniqueId", clean_username),
                "nickname": user.get("nickname", clean_username),
                "bio": user.get("signature", "Sin biografía."),
                "bio_link": user.get("bioLink", {}).get("link", ""), # external link in bio
                "verified": user.get("verified", False),
                "is_private": user.get("privateAccount", False),     # private account
                "avatar_url": user.get("avatarLarger") or user.get("avatarMedium") or user.get("avatarThumb", ""),
                "followers": stats.get("followerCount", 0),
                "following": stats.get("followingCount", 0),
                "likes": stats.get("heartCount", 0),
                "video_count": stats.get("videoCount", 0),
            }

            _profile_cache[clean_username] = {
                "data": result,
                "timestamp": now
            }
            _save_cache(_profile_cache)

            return result

        except Exception as e:
            print(f"[Exception] while fetching @{clean_username}: {e}")
            return _profile_cache.get(clean_username, {}).get("data")