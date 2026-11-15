#!/usr/bin/env python3
"""bt01 採点：モデルごとの「分岐の地図」を、作者の正解表と突き合わせる

  python3 tools/score.py BOX_OR_RESULTS... [TEXT.md]
    BOX_OR_RESULTS  箱のフォルダ・results/・json のどれでも、いくつでも
    TEXT.md         引用の照合に使う本文（省略時は正解表の text）

出力：標準出力に表、箱の並ぶフォルダに bt01_SCORE.md（正解に当たらなかった候補も、人が読む用に全部並べる）
混入の疑い：本文に無く設定資料にだけある語が答えに出たら ⚠。ハーネスのログで、本文以外を開いていないかを確かめる
"""
import sys, os, json, re
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLD = yaml.safe_load(open(os.path.join(ROOT, "gold", "GOLD.yaml"), encoding="utf-8"))

# 本文に一度も出ず、設定資料にだけある語。答えに出たら、本文以外を読んだ疑い（人が確かめる）
CANARY = ["月の森", "聞き耳", "メルヒオル", "ハンネ", "カルトブルン", "古砦", "エーリカ", "無縁墓地", "二一二年", "命令書", "川原の小石", "長老会"]

def norm(s):
    return re.sub(r"[\s　「」『』]", "", s or "")

def load(p):
    t = open(p, encoding="utf-8").read().strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)          # コードの囲みを外す
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0))

def blob(pt):
    parts = [pt.get("quote", ""), pt.get("question", "")]
    for v in pt.get("values", []) or []:
        parts += [str(v.get("value", "")), str(v.get("converges_to", ""))]
    return "\n".join(parts)

def hit(g, text):
    m = g["match"]
    return all(k in text for k in m.get("all", [])) and (not m.get("any") or any(k in text for k in m["any"]))

def score(path, body):
    d = load(path); pts = d.get("points", [])
    rows, matched_pts = {}, set()
    for g in GOLD["gold"]:
        for i, pt in enumerate(pts):
            if hit(g, blob(pt)):
                rows[g["id"]] = (pt.get("rank", i + 1), pt); matched_pts.add(i); break
    wsum = sum(g["weight"] for g in GOLD["gold"])
    got = sum(g["weight"] for g in GOLD["gold"] if g["id"] in rows)
    verbatim = sum(1 for pt in pts if norm(pt.get("quote")) and norm(pt.get("quote"))[:40] in norm(body))
    # G1 の深さ：別の値（alt）と、見分けの手がかり（カフス・白い布）
    g1 = rows.get("G1", (None, {}))[1]
    g1_alt = any(v.get("reading") == "alt" for v in g1.get("values", []) or [])
    g1_spr = "\n".join(g1.get("sprouts", []) or []) + blob(g1)
    g1_sprouts = [s for s in ["カフス", "白い布"] if s in g1_spr]
    raw = open(path, encoding="utf-8").read()
    canary = [w for w in CANARY if w in raw and w not in body]
    return {
        "canary": canary,
        "model": d.get("model") or os.path.basename(path),
        "file": os.path.basename(path),
        "n": len(pts),
        "recall_w": round(got / wsum, 2),
        "ranks": {g["id"]: rows[g["id"]][0] if g["id"] in rows else None for g in GOLD["gold"]},
        "g1_alt": g1_alt, "g1_sprouts": g1_sprouts,
        "verbatim": f"{verbatim}/{len(pts)}",
        "extras": [(pt.get("rank", i + 1), pt.get("question", ""), pt.get("quote", "")) for i, pt in enumerate(pts) if i not in matched_pts],
        "overall": d.get("overall", ""),
    }

def main():
    args = sys.argv[1:]
    tp = args.pop() if args and args[-1].endswith(".md") else os.path.join(ROOT, "..", "..", "..", GOLD["text"])
    body = open(tp, encoding="utf-8").read() if os.path.exists(tp) else ""
    files = []
    for a in args:   # 箱のフォルダ、results/ フォルダ、json ファイルのどれでもよい
        if a.endswith(".json"): files.append(a); continue
        d = os.path.join(a, "results") if os.path.isdir(os.path.join(a, "results")) else a
        files += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith(".json")]
    rd = os.path.dirname(os.path.abspath(files[0])) if files else "."
    res = []
    for f in files:
        try: res.append(score(f, body))
        except Exception as e: print(f"読めない {f}: {e}")
    ids = [g["id"] for g in GOLD["gold"]]
    head = "| モデル | 件数 | 重み付き再現率 | " + " | ".join(ids) + " | G1の別値 | G1の芽 | 引用の正確さ | 混入の疑い |"
    line = "|" + "---|" * (len(ids) + 7)
    out = [head, line]
    for r in sorted(res, key=lambda r: -r["recall_w"]):
        out.append(f"| {r['model']} | {r['n']} | {r['recall_w']} | " + " | ".join(str(r["ranks"][i] or "—") for i in ids)
                   + f" | {'○' if r['g1_alt'] else '×'} | {'・'.join(r['g1_sprouts']) or '—'} | {r['verbatim']} | {'⚠ ' + '・'.join(r['canary']) if r['canary'] else '—'} |")
    print("\n".join(out))
    md = ["# bt01 採点", "", "数字はその正解に当たった分岐点の順位（—は見つけていない）。", "",
          *[f"- {g['id']}（重み{g['weight']}）{g['title']}" for g in GOLD["gold"]], "", *out, ""]
    for r in res:
        md += [f"## {r['model']}", "", f"全体の見立て：{r['overall']}", "", "### 正解表に無い候補（人が読んで、新しい発見かを判定する）", ""]
        md += [f"- {k}位：{q}　『{qt[:60]}』" for k, q, qt in r["extras"]] or ["- なし"]
        md.append("")
    p = os.path.join(os.path.dirname(os.path.dirname(rd)), "bt01_SCORE.md")
    open(p, "w", encoding="utf-8").write("\n".join(md)); print("→", p)

if __name__ == "__main__":
    main()
