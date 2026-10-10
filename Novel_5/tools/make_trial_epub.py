#!/usr/bin/env python3
"""試読版EPUB：同じ CANON から書かれた3つの原稿を1冊にまとめる（縦書き・右綴じ、作者は伏せて巻末で明かす）。
  python3 tools/make_trial_epub.py   → output/星を汚す者_試読版.epub
"""
import datetime
import html
import re
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE = "星を汚す者"
VERSIONS = [  # 表示名, 書き手, 原稿の場所（作者は巻末まで伏せる）
    ("原稿Ａ", "openai/gpt-6-luna-pro（OpenRouter）", "runs/lunapro/r1"),
    ("原稿Ｂ", "Claude Opus 5.5（Antigravity CLI・Medium）", "runs/opus_agy/r1"),
    ("原稿Ｃ", "anthropic/claude-haiku-5.5（OpenRouter）", "runs/haiku/r2"),
]
KANJI = ["〇", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def esc(s):
    return html.escape(s, quote=True)


def tcy(s):
    s = esc(s)
    s = re.sub(r"(?<![0-9A-Za-z])([0-9]{1,3})(?![0-9A-Za-z])", r'<span class="tcy">\1</span>', s)
    return re.sub(r"(!\?|\?!|!!|\?\?)", r'<span class="tcy">\1</span>', s)


def paragraphs(body):
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.fullmatch(r"[＊*◇◆・―\-]{1,}[ 　＊*◇◆]*", line):
            out.append('<p class="break">＊</p>')
        elif line[0] in "「『（(―…〈":
            out.append(f'<p class="talk">{tcy(line)}</p>')
        else:
            out.append(f"<p>{tcy(line)}</p>")
    return "\n".join(out)


def page(title, body, cls=""):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ja" lang="ja">
<head><meta charset="UTF-8"/><title>{esc(title)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head>
<body class="{cls}">
{body}
</body>
</html>
"""


CSS = """@charset "UTF-8";
html { writing-mode: vertical-rl; -webkit-writing-mode: vertical-rl; -epub-writing-mode: vertical-rl; }
body { margin: 0; font-family: "Hiragino Mincho ProN", "YuMincho", "Yu Mincho", "Noto Serif CJK JP", "Noto Serif JP", serif-ja, serif; line-height: 1.8; text-align: justify; }
h1, h2, h3 { font-weight: normal; }
h2.chapter { font-size: 1.3em; margin-left: 3em; margin-top: 2em; }
h2.chapter .no { display: block; font-size: 0.8em; margin-bottom: 0.5em; }
p { margin: 0; text-indent: 1em; }
p.talk { text-indent: 0; }
p.break { text-indent: 0; text-align: center; margin: 0 1em; }
.tcy { text-combine-upright: all; -webkit-text-combine: horizontal; -epub-text-combine: horizontal; }
body.titlepage { text-align: center; }
body.titlepage h1 { font-size: 2em; margin-top: 30%; }
body.titlepage .sub { margin-top: 2em; }
body.part h1 { font-size: 1.8em; margin-top: 35%; }
body.note p, body.colophon p { text-indent: 0; margin-left: 0.6em; }
"""


def image_page(href, w, h):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="ja" lang="ja">
<head><meta charset="UTF-8"/><title>表紙</title>
<style>html,body{{margin:0;padding:0;height:100%;writing-mode:horizontal-tb;}} svg{{display:block;}}</style></head>
<body epub:type="cover">
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1" width="100%" height="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet">
<image width="{w}" height="{h}" xlink:href="{href}"/>
</svg>
</body>
</html>
"""


def load(d):
    chs = []
    for n in range(1, 6):
        t = (ROOT / d / f"ch{n:02d}.md").read_text(encoding="utf-8").strip()
        first, _, body = t.partition("\n")
        m = re.match(r"#\s*第.+?章[\s　]*(.*)", first)
        chs.append((n, m.group(1).strip() if m else "", body.strip()))
    return chs


def build():
    files, manifest, spine, nav = {}, [], [], []
    files["OEBPS/style.css"] = CSS
    cover = ROOT / "images" / "cover_trial.jpg"
    images = {}
    if cover.exists():
        images["OEBPS/images/cover.jpg"] = cover.read_bytes()
        manifest.append('<item id="cover-img" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>')
        files["OEBPS/cover.xhtml"] = image_page("images/cover.jpg", 1600, 2560)
        manifest.append('<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml" properties="svg"/>')
        spine.append('<itemref idref="cover"/>')

    def add(pid, fname, title, body, cls="", toc=None):
        files[f"OEBPS/{fname}"] = page(title, body, cls)
        manifest.append(f'<item id="{pid}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{pid}"/>')
        if toc:
            nav.append((toc, fname))

    add("title", "title.xhtml", TITLE, f"<h1>{TITLE}</h1><p class=\"sub\">試読版　三つの原稿</p>", "titlepage")
    intro = ["<h2>この本について</h2>",
             "<p>同じ設定資料（薄いCANON）から、三つの生成AIがそれぞれ書いた短編SFの原稿を、一冊にまとめた試読版です。</p>",
             "<p>筋書きの骨組み、章立て、結末の方向は共通です。人物の名前、惑星の細部、汚染を止める科学的な手段は、書き手がそれぞれ決めています。</p>",
             "<p>先入観なく読み比べていただくため、書き手の名前は巻末まで伏せています。</p>",
             "<p>各原稿は、校正役（Claude Opus 5.5）の指摘を受けて一〜二回の改稿を経たものです。公開用ではありません。</p>"]
    add("intro", "intro.xhtml", "この本について", "\n".join(intro), "note", "この本について")
    total = {}
    for vi, (label, writer, d) in enumerate(VERSIONS, 1):
        chs = load(d)
        total[label] = sum(len(re.sub(r"\s", "", b)) for _, _, b in chs)
        add(f"part{vi}", f"part{vi}.xhtml", label, f"<h1>{label}</h1><p class=\"sub\">{TITLE}</p>", "part titlepage", label)
        for n, ct, body in chs:
            head = f'<h2 class="chapter"><span class="no">第{KANJI[n]}章</span>{esc(ct)}</h2>'
            add(f"v{vi}c{n}", f"v{vi}_ch{n:02d}.xhtml", f"{label} 第{n}章 {ct}", head + "\n" + paragraphs(body), toc=f"{label}　第{KANJI[n]}章　{ct}")
    reveal = ["<h2>書き手の対応表</h2>"] + [f"<p>{label}　……　{esc(w)}（本文 約{total[label]:,}字）</p>" for label, w, _ in VERSIONS]
    reveal += ["<p>設定資料（CANON）と章立て：Claude Opus 5.5</p>", "<p>企画：企画コンペ優勝案（openai/gpt-6-luna-pro）を人の講評で改稿</p>", "<p>校正・監査：Claude Opus 5.5</p>"]
    add("reveal", "reveal.xhtml", "書き手の対応表", "\n".join(reveal), "note", "書き手の対応表")
    col = [f"<h2>{TITLE}　試読版</h2>", "<p>本書の本文はすべて生成AIによって書かれました。</p>", "<p>表紙の絵は、プログラムで描いた画像です。</p>",
           f"<p>{datetime.date.today().isoformat()}　作成（非公開・試読用）</p>"]
    add("colophon", "colophon.xhtml", "奥付", "\n".join(col), "colophon", "奥付")
    items = "".join(f'<li><a href="{f}">{esc(t)}</a></li>' for t, f in nav)
    files["OEBPS/nav.xhtml"] = page("目次", f'<nav epub:type="toc" id="toc"><h2>目次</h2><ol>{items}</ol></nav>')
    book_id = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "novel5-trial:" + TITLE))
    pts = "".join(f'<navPoint id="np{i}" playOrder="{i}"><navLabel><text>{esc(t)}</text></navLabel><content src="{f}"/></navPoint>' for i, (t, f) in enumerate(nav, 1))
    files["OEBPS/toc.ncx"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ja">
<head><meta name="dtb:uid" content="{book_id}"/></head>
<docTitle><text>{TITLE}</text></docTitle>
<navMap>{pts}</navMap>
</ncx>
"""
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files["OEBPS/content.opf"] = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ja" prefix="rendition: http://www.idpf.org/vocab/rendition/#">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{book_id}</dc:identifier>
<dc:title>{TITLE}（試読版・三つの原稿）</dc:title>
<dc:language>ja</dc:language>
<dc:creator>AI制作スタジオ（試読用）</dc:creator>
<meta property="dcterms:modified">{now}</meta>
<meta name="primary-writing-mode" content="vertical-rl"/>
<meta name="cover" content="cover-img"/>
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
<item id="css" href="style.css" media-type="text/css"/>
{chr(10).join(manifest)}
</manifest>
<spine toc="ncx" page-progression-direction="rtl">
{chr(10).join(spine)}
</spine>
</package>
"""
    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    out = ROOT / "output" / f"{TITLE}_試読版.epub"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, compress_type=zipfile.ZIP_DEFLATED)
        for k, v in files.items():
            z.writestr(k, v, compress_type=zipfile.ZIP_DEFLATED)
        for k, v in images.items():
            z.writestr(k, v, compress_type=zipfile.ZIP_STORED)
    print(out, {k: v for k, v in total.items()})


if __name__ == "__main__":
    build()
