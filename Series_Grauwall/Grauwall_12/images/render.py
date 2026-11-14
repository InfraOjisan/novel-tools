import os
from playwright.sync_api import sync_playwright
from PIL import Image
os.chdir(os.path.dirname(os.path.abspath(__file__)))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 2560})
    pg.on("pageerror", lambda e: print("JS ERROR", e))
    pg.goto(f"file://{os.getcwd()}/art_source.html#a", wait_until="commit")
    pg.wait_for_function("document.title==='done'", timeout=180000); pg.wait_for_timeout(500)
    pg.locator("#stage").screenshot(path="cover.png")
    b.close()
Image.open("cover.png").convert("RGB").save("cover.jpg", quality=90)
