import os, sys
from playwright.sync_api import sync_playwright
from PIL import Image
# 第6回『白塔の使者』表紙候補。art_source.html を #a/#b/#c/#d で描き分けて 1600x2560 で撮影する
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.makedirs("cover_candidates", exist_ok=True)
modes = sys.argv[1:] or ["a","b","c","d"]
names={"a":"cover_A_toudai","b":"cover_B_shishuu","c":"cover_C_futatsu_no_hi","d":"cover_D_houe_to_hi"}
with sync_playwright() as p:
    b = p.chromium.launch()
    for m in modes:
        pg = b.new_page(viewport={"width":1600,"height":2560})
        pg.on("pageerror", lambda e: print("JS ERROR", e))
        pg.goto(f"file://{os.getcwd()}/art_source.html#{m}", wait_until="commit")
        pg.wait_for_function("document.title==='done'", timeout=120000); pg.wait_for_timeout(300)
        out = f"cover_candidates/{names[m]}"
        pg.locator("#stage").screenshot(path=out + ".png")
        pg.close()
        Image.open(out + ".png").convert("RGB").save(out + ".jpg", quality=90)
        os.remove(out + ".png")
    b.close()
ims=[Image.open(f"cover_candidates/{names[m]}.jpg").resize((400,640)) for m in ["a","b","c","d"] if os.path.exists(f"cover_candidates/{names[m]}.jpg")]
sheet=Image.new("RGB",(400*len(ims)+40*(len(ims)+1),720),(240,240,240))
for i,im in enumerate(ims): sheet.paste(im,(40+i*440,40))
sheet.save("cover_candidates/表紙候補_比較.jpg",quality=88)
