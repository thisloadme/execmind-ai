"""Service for browser automation tasks using Playwright."""

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from app.utils.logging import get_logger

logger = get_logger("browser_service")

class BrowserService:
    """Handles browser automation requests."""

    async def play_youtube_music(self) -> dict:
        """Navigates to YouTube Music and attempts to play the last played track."""
        # We launch without 'async with' to keep the browser alive for music
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        
        try:
            logger.info("navigating_to_youtube_music")
            await page.goto("https://music.youtube.com", wait_until="networkidle")
            
            # YT Music often has a 'Listen again' shelf. 
            # We try to click the first item's overlay/play button.
            play_button_selector = "ytmusic-shelf-renderer:has-text('Listen again') #play-button, ytmusic-item-section-renderer #play-button, .play-button"
            try:
                await page.wait_for_selector(play_button_selector, timeout=10000)
                buttons = await page.query_selector_all(play_button_selector)
                if buttons:
                    await buttons[0].click()
                    logger.info("play_button_clicked")
                    await asyncio.sleep(2)
                    return {"status": "success", "message": "Berhasil memutar lagu terakhir di YouTube Music."}
                else:
                    return {"status": "error", "message": "Tidak dapat menemukan tombol putar di YouTube Music."}
            except Exception as e:
                logger.error("play_error", error=str(e))
                return {"status": "partial_success", "message": "Halaman dibuka, tapi tidak dapat memulai pemutaran otomatis secara spesifik."}
                
        except Exception as e:
            logger.error("navigation_error", error=str(e))
            return {"status": "error", "message": f"Gagal membuka YouTube Music: {str(e)}"}

    async def play_youtube_music_background(self):
        """Runs the playback in a way that preserves the browser (fire and forget)."""
        asyncio.create_task(self.play_youtube_music_and_persist())

    async def play_youtube_music_and_persist(self):
        """Opens browser and stays open."""
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        await page.goto("https://music.youtube.com", wait_until="networkidle")
        
        play_button_selector = "ytmusic-shelf-renderer:has-text('Listen again') #play-button, ytmusic-item-section-renderer #play-button, .play-button, ytmusic-play-button-renderer"
        try:
            await page.wait_for_selector(play_button_selector, timeout=15000)
            buttons = await page.query_selector_all(play_button_selector)
            if buttons:
                await buttons[0].click()
        except:
            pass
