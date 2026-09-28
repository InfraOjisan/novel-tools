#!/usr/bin/env python3
"""proofread_apply — 校正指示（EDITS）を当てて、校正版を別ファイルとして書き出す。原稿は変更しない。

  python3 tools/proofread_apply.py

入力:  polished/chNN.md（文体仕上げ稿）。なければ chapters/chNN.md
出力:
  output/final_proofread.md       校正版の結合原稿（make_epub.py --source proofread の入力）
  output/proofread_changes.md     適用した修正の一覧（章ごと・原文→修正・理由）

分類:
  誤字   … 誤変換・旧字・誤った語
  表現   … 意味が通りにくい、不自然な言い回し（仕上げで入った癖の整理を含む）
  連続性 … 同じ章や前後の章の描写との食い違い
  設定   … CANON・LEDGER の事実に戻すための最小限の修正
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
N_CH = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["chapters"]

# (章, 原文, 修正, 分類, 理由)
EDITS = [
    # (1, "原文", "修正", "誤字", "理由"),
]


def main():
    canon = (ROOT / "canon" / "CANON.md").read_text(encoding="utf-8")
    m = re.search(r"タイトル：\s*(.+)", canon)
    title = m.group(1).strip().strip("『』「」") if m else "無題"
    log, parts, missing = [], [], []
    for n in range(1, N_CH + 1):
        src = ROOT / "polished" / f"ch{n:02d}.md"
        if not src.exists():
            src = ROOT / "chapters" / f"ch{n:02d}.md"
        text = src.read_text(encoding="utf-8")
        for ch, old, new, cat, why in EDITS:
            if ch != n:
                continue
            c = text.count(old)
            if c != 1:
                missing.append(f"第{n}章: 見つからない/複数（{c}件）: {old[:30]}")
                continue
            text = text.replace(old, new)
            log.append((n, cat, old, new or "（削除）", why))
        text = re.sub(r"[ \t]+\n", "\n", text)
        parts.append(text.strip().replace("# 第", "## 第", 1))
    out = ROOT / "output" / "final_proofread.md"
    out.write_text(f"# {title}\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")

    lines = ["# 適用した修正の一覧", "", "対象：polished/chNN.md（Aion 仕上げ稿）→ output/final_proofread.md（原稿は変更していません）", ""]
    cats = {}
    for n, cat, *_ in log:
        cats[cat] = cats.get(cat, 0) + 1
    lines.append("件数：" + "　".join(f"{k} {v}件" for k, v in sorted(cats.items())))
    cur = None
    for n, cat, old, new, why in log:
        if n != cur:
            lines += ["", f"## 第{n}章", "", "| 分類 | 原文 | 修正 | 理由 |", "|---|---|---|---|"]
            cur = n
        esc = lambda s: s.replace("|", "｜").replace("\n", "⏎")
        lines.append(f"| {cat} | {esc(old)} | {esc(new)} | {esc(why)} |")
    if missing:
        lines += ["", "## 当てられなかった修正", ""] + [f"- {x}" for x in missing]
    (ROOT / "output" / "proofread_changes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    body_chars = sum(len(re.sub(r"\s", "", p.split("\n", 1)[1])) for p in parts)
    print(f"output/final_proofread.md（本文{body_chars}字）と output/proofread_changes.md を作成。適用{len(log)}件、失敗{len(missing)}件")
    for x in missing:
        print("  未適用:", x)


if __name__ == "__main__":
    main()
