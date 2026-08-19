import json
import time
from playwright.async_api import async_playwright

_browser_instance = None
_playwright_obj = None
_profile_cache = {}
CACHE_TTL = 600

async def get_browser():
    global _browser_instance, _playwright_obj
    if _browser_instance is None or not _browser_instance.is_connected():
        _playwright_obj = await async_playwright().start()
        _browser_instance = await _playwright_obj.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled", # Oculta la automatización de Blink
            ]
        )
    return _browser_instance

async def get_user_profile_info_playwright(username: str):
    clean_username = username.lstrip("@").lower()
    now = time.time()

    if clean_username in _profile_cache:
        data, timestamp = _profile_cache[clean_username]
        if now - timestamp < CACHE_TTL:
            return data

    browser = await get_browser()
    
    # Creamos un contexto con argumentos stealth inyectados a nivel de navegador
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
        locale="es-ES",
        timezone_id="America/Bogota"
    )

    # Inyección de Scripts Anti-Detection antes de cargar cualquier script de TikTok
    await context.add_init_script("""
        // Sobrescribir navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Simular lenguajes del navegador
        Object.defineProperty(navigator, 'languages', {
            get: () => ['es-ES', 'es', 'en-US', 'en']
        });

        // Simular Chrome runtime
        window.chrome = {
            runtime: {}
        };
    """)

    page = await context.new_page()

    # Bloquear recursos pesados para ahorrar ancho de banda y RAM
    await page.route("**/*.{png,jpg,jpeg,svg,webp,css,woff,woff2}", lambda route: route.abort())

    try:
        url = f"https://www.tiktok.com/@{clean_username}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        script_content = await page.evaluate('''() => {
            const el = document.getElementById("__UNIVERSAL_DATA_FOR_REHYDRATION__");
            return el ? el.textContent : null;
        }''')

        await page.close()
        await context.close()

        if not script_content:
            print(f"No se encontró el script en el DOM de @{clean_username}")
            return None

        data = json.loads(script_content)
        user_detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
        user_info = user_detail.get("userInfo", {}).get("user", {})
        stats = user_detail.get("userInfo", {}).get("stats", {})

        if not user_info:
            return None

        result = {
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

        _profile_cache[clean_username] = (result, now)
        return result

    except Exception as e:
        print(f"Error scraping @{clean_username}: {e}")
        try:
            await page.close()
            await context.close()
        except Exception:
            pass
        return None