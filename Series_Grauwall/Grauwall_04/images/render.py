import os, sys
from playwright.sync_api import sync_playwright
from PIL import Image
# 第4回『豆のスープ』表紙候補。art_source.html を #a/#b/#c で描き分けて 1600x2560 で撮影する
os.chdir(os.path.dirname(os.path.abspath(__file__)))
modes = sys.argv[1:] or ["a","b","c"]
names={"a":"cover_A_soup_mimikage","b":"cover_B_yuki_mimi","c":"cover_C_ishoubako"}
with sync_playwright() as p:
    b = p.chromium.launch()
    for m in modes:
        pg = b.new_page(viewport={"width":1600,"height":2560})
        pg.goto(f"file://{os.getcwd()}/art_source.html#{m}", wait_until="commit")
        pg.wait_for_function("document.title==='done'"); pg.wait_for_timeout(300)
        pg.locator("#stage").screenshot(path=f"{names[m]}.png")
        pg.close()
        Image.open(f"{names[m]}.png").convert("RGB").save(f"{names[m]}.jpg", quality=90)
        os.remove(f"{names[m]}.png")
    b.close()
ims=[Image.open(f"{names[m]}.jpg").resize((400,640)) for m in ["a","b","c"] if os.path.exists(f"{names[m]}.jpg")]
sheet=Image.new("RGB",(400*len(ims)+40*(len(ims)+1),720),(240,240,240))
for i,im in enumerate(ims): sheet.paste(im,(40+i*440,40))
sheet.save("表紙候補_比較.jpg",quality=88)
