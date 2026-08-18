import json
import re
import aiohttp
from bs4 import BeautifulSoup

async def get_user_profile_info(username: str):
    """
    Scrapea la página pública de TikTok de un usuario para extraer su perfil,
    esté o no en transmisión en vivo.
    """
    clean_username = username.lstrip("@")
    url = f"https://www.tiktok.com/@{clean_username}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    print(f"Error HTTP {response.status} al consultar @{clean_username}")
                    return None
                
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        
        # TikTok guarda todos los datos del perfil en una etiqueta <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">
        script_tag = soup.find("script", id="__UNIVERSAL_DATA_FOR_REHYDRATION__")
        
        if not script_tag or not script_tag.string:
            print("No se encontró el bloque de datos en la página.")
            return None

        data = json.loads(script_tag.string)
        default_scope = data.get("__DEFAULT_SCOPE__", {})
        user_detail = default_scope.get("webapp.user-detail", {})
        
        user_info = user_detail.get("userInfo", {}).get("user", {})
        stats = user_detail.get("userInfo", {}).get("stats", {})

        if not user_info:
            return None

        return {
            "username": clean_username,
            "nickname": user_info.get("nickname", clean_username),
            "bio": user_info.get("signature", "Sin biografía."),
            "verified": user_info.get("verified", False),
            "avatar_url": user_info.get("avatarLarger") or user_info.get("avatarMedium") or "",
            "followers": stats.get("followerCount", 0),
            "following": stats.get("followingCount", 0),
            "likes": stats.get("heartCount", 0),
            "video_count": stats.get("videoCount", 0),
        }

    except Exception as e:
        print(f"Error extrayendo el perfil de @{clean_username}: {e}")
        return None