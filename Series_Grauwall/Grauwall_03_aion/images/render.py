import sys
from playwright.sync_api import sync_playwright
from PIL import Image
modes = sys.argv[1:] or ["a","b","c"]
names={"a":"cover_A_ichirizuka","b":"cover_B_takibi","c":"cover_C_yuugure"}
with sync_playwright() as p:
    b = p.chromium.launch()
    for m in modes:
        pg = b.new_page(viewport={"width":1600,"height":2560})
        pg.goto(f"file://{__import__('os').getcwd()}/art_source.html#{m}", wait_until="commit")
        pg.wait_for_function("document.title==='done'"); pg.wait_for_timeout(300)
        pg.locator("#stage").screenshot(path=f"{names[m]}.png")
        pg.close()
        Image.open(f"{names[m]}.png").convert("RGB").save(f"{names[m]}.jpg", quality=90)
    b.close()
ims=[Image.open(f"{names[m]}.jpg").resize((400,640)) for m in ["a","b","c"] if __import__('os').path.exists(f"{names[m]}.jpg")]
sheet=Image.new("RGB",(400*len(ims)+40*(len(ims)+1),720),(240,240,240))
for i,im in enumerate(ims): sheet.paste(im,(40+i*440,40))
sheet.save("表紙候補_比較.jpg",quality=88)
