#!/usr/bin/env python3
"""bt02 第1段の答えを束ねて「決定論的でない事象の一覧」（SIGNALS.md）を作る

  python3 tools/merge.py OUT.md TEXT.md RESULT.json...

- 正解表は使わない（束ね方に作者の誘導を入れないため）。機械的に、本文の位置で束ねるだけ。
- 各分岐点の quote を本文で探し、位置の近いもの（既定 150 字以内）を一つの事象にまとめる。
- 事象ごとに「何本のモデルが挙げたか」（検出の多数決）と、各モデルの問い・別の値・芽を並べる。
- モデル名は伏せて A〜F の記号にする（第2段のモデルが、名前で重みを変えないように）。
"""
import sys, os, re, json

GAP = 150

def norm(s):
    return re.sub(r"[\s　「」『』…、。！？!?]", "", s or "")

def load(p):
    t = open(p, encoding="utf-8").read().strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    t = re.search(r"\{.*\}", t, re.S).group(0)
    try:
        return json.loads(t, strict=False)
    except json.JSONDecodeError:
        # よくある崩れ：配列の最後の文字列の閉じ引用符が抜けている（…」], のような行）
        fixed = []
        for line in t.split("\n"):
            if line.count('"') % 2 == 1 and re.search(r"[^\"]\],?\s*$", line):
                line = re.sub(r"\](,?)\s*$", r'"]\1', line)
            fixed.append(line)
        return json.loads("\n".join(fixed), strict=False)

def main():
    out, textp, files = sys.argv[1], sys.argv[2], sys.argv[3:]
    body = open(textp, encoding="utf-8").read()
    nb = norm(body)
    # 章の境目（正規化後の位置）
    heads = [(len(norm(body[:m.start()])), m.group(1)) for m in re.finditer(r"^## (第\d+章[^\n]*)", body, re.M)]
    def chapter(pos):
        c = ""
        for p, h in heads:
            if p <= pos: c = h
        return c
    items = []
    for k, f in enumerate(files):
        tag = "ABCDEFGHIJ"[k]
        d = load(f)
        for pt in d.get("points", []):
            q = norm(pt.get("quote"))
            pos = nb.find(q[:30]) if q else -1
            if pos < 0 and len(q) > 12: pos = nb.find(q[:12])
            items.append({"tag": tag, "pos": pos, "pt": pt})
    found = sorted([i for i in items if i["pos"] >= 0], key=lambda i: i["pos"])
    lost = [i for i in items if i["pos"] < 0]
    groups = []
    for it in found:
        if groups and it["pos"] - groups[-1][-1]["pos"] <= GAP:
            groups[-1].append(it)
        else:
            groups.append([it])
    L = ["# 決定論的でない事象の一覧", "",
         f"同じ原文を、{len(files)}本の下読み（A〜{'ABCDEFGHIJ'[len(files)-1]}）が別々に読み、「結末や解釈を揺らせる箇所」を挙げたものを、原文の位置で束ねた。",
         "「挙げた数」は、その箇所を独立に挙げた下読みの数。多いほど目立つ箇所、少ないほど見落とされやすい箇所。", "",
         f"事象 {len(groups)} 件（原文の順）", ""]
    for n, g in enumerate(groups, 1):
        tags = sorted({i["tag"] for i in g})
        L += [f"## 事象{n}　{chapter(g[0]['pos'])}　挙げた数 {len(tags)}（{'・'.join(tags)}）", "",
              f"原文：『{g[0]['pt'].get('quote', '')}』", ""]
        for i in g:
            pt = i["pt"]
            L.append(f"- **{i['tag']}** 問い：{pt.get('question', '')}")
            for v in pt.get("values", []) or []:
                mark = "表" if v.get("reading") == "surface" else "別"
                L.append(f"    - {mark}：{v.get('value', '')}")
            spr = [s for s in (pt.get("sprouts") or []) if s]
            if spr: L.append("    - 見分けの手がかり（下読みの案）：" + "／".join(f"『{s}』" for s in spr))
        L.append("")
    if lost:
        L += ["## 位置を特定できなかった指摘", ""]
        for i in lost:
            L.append(f"- **{i['tag']}** {i['pt'].get('question', '')}（引用：『{i['pt'].get('quote', '')[:40]}』）")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"merge: {len(items)} 点 → 事象 {len(groups)} 件、位置不明 {len(lost)} 点 → {out}")

if __name__ == "__main__":
    main()
