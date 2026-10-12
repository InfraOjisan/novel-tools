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
    # ---- グラウヴァル第6回『白塔の使者』校正（2026-10-12, Claude Opus 5.5 による全文通読）
    (4, '「偉そうにしてますよ」とダリオが言った。', '「偉そうにしてるさ」とダリオが言った。', '連続性', 'ダリオは誰に対しても常体（プロデューサー指摘 2026-10-12）'),
    (5, '「ありがとう、剣士さん。髭の端が、まだ少し縮れていますね」', '「ありがとうございます、剣士さん。髭の端が、まだ少し縮れていますね」', '表現', 'エルノは人前では誰に対しても丁寧（CANON 呼び方の規則）'),
    (7, '「数えました」', '「数えた」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (7, '「少しは寝ます。嘘はつけませんので、先に言っておきます」', '「少しは寝ます。嘘はつきませんので、先に言っておきます」', '設定', 'テオは誓願で嘘を「つかない」（つけないのは亜人）。設定資料2-1'),
    (9, 'すかさず、ダリオのブーツがその鉤を踏んだ。', 'すかさず、ダリオの靴がその鉤を踏んだ。', '表現', '外来語を避ける（シリーズの語彙）'),
    (9, 'ブーツの踵に、塩漬けの魚の汁が黒く乾きかけていた。', '靴の踵に、塩漬けの魚の汁が黒く乾きかけていた。', '表現', '外来語を避ける（シリーズの語彙）'),
    (9, '膝の下の石が冷たく、ズボンの生地に水が染みた。', '膝の下の石が冷たく、脚を包む布に水が染みた。', '表現', '外来語を避ける（シリーズの語彙）'),
    (10, '「ないよ」賢者は穏やかに言った。', '「ありません」賢者は穏やかに言った。', '連続性', 'エルノは人前では誰に対しても丁寧（第2章、CANON 呼び方の規則）'),
    (13, '「干し棚の裏です。肉を持って」', '「干し棚の裏だ。肉を持って」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「あなたの肉かは、分かりません」', '「誰の肉かは、分からない」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「止めろとは、言われていませんでした」', '「止めろとは、言われていなかった」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「舟宿の裏で会っていました。白い手袋から指輪の男へ、布の包みが渡りました。指輪の男は帳面を見せて、頁を繰りました」', '「舟宿の裏で会っていた。白い手袋から指輪の男へ、布の包みが渡った。指輪の男は帳面を出して、頁を繰った」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「聞こえませんでした」', '「聞こえなかった」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「はい。見えたことだけです」', '「そうだ。見えたことだけだ」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「取り替えたように見えました」ケスは梁から言った。', '「取り替えたように見えた」ケスは梁から言った。', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「止めろとは、言われていません」', '「止めろとは、言われていない」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「白い手袋の男は、まだ決めていないと言った」\n\n「はい」', '「白い手袋の男は、まだ決めていないと言った」\n\n「言った」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「見ていません。嘘かどうかは、分かりません」', '「見ていない。嘘かどうかは、分からない」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (13, '「はい。親方が先に日を言ったことと、あの人が後から決めると言ったことです」', '「そうだ。親方が先に日を言ったことと、あの男が後から決めると言ったことだ」', '連続性', 'ケスの台詞は短い常体（第3・6章、CANON 呼び方の規則）'),
    (18, '「僕は、嘘をつけないので」', '「僕は、嘘をつきませんので」', '設定', 'テオは誓願で嘘を「つかない」（つけないのは亜人）。設定資料2-1'),
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

    lines = ["# 適用した修正の一覧", "", "対象：chapters/chNN.md（確定稿）→ output/final_proofread.md（原稿は変更していません）", ""]
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
