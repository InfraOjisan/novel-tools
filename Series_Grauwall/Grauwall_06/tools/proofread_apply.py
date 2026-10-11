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
    # ---- グラウヴァル第2回『新しい組合長』校正（2026-10-02, Claude）
    (2, "その次が、カウンターの端の茶碗を両手で包んでいる組合長だろう。", "その次が、カウンターの端で登録簿に屈みこんでいる組合長だろう。", "連続性", "第2章の昼のエーリカは茶碗を持っていない（登録簿を読んでいる）"),
    (2, "指に、蝋の欠けらが少しついた。", "指に、蝋のかけらが少しついた。", "誤字", "「欠けら」は誤った表記。「かけら」に"),
    (3, "昨日の夕方から封を切らずにいた、参事会の書状だ。封蝋は、もう割れていた。いつ割ったのかは知らない。夜のあいだの、どこかの七歩の途中だろう。", "半刻前に届いて、封を切らずにいた参事会の書状だ。封蝋は、もう割れていた。いつ割ったのかは知らない。二階へ上がっていた、その半刻のあいだのどこかだろう。", "連続性", "書状が届いたのは同じ二十三日の夕方五つ半（第2章）。第3章は同日の六つで、夜はまだ越えていない"),
    (6, "残っていたじゃがいもの欠けらを", "残っていたじゃがいものかけらを", "誤字", "「欠けら」は誤った表記。「かけら」に"),
    (7, "「隊長がいると、だいたい揉めないんで」\n\n「来るのは、どなたです」", "「隊長がいると、だいたい揉めないんで」\n\nそれは本当だろう、と俺は思った。\n\n「来るのは、どなたです」", "連続性", "加筆の際に、トマスの「揉めない」を受ける一文が後ろへ取り残されていたのを元の位置へ戻す"),
    (7, "エーリカはそれ以上何も言わず、帳面に目を戻した。\n\nそれは本当だろう、と俺は思った。\n\nカウンターの端で、エーリカが帳面を広げていた。今朝から、組合の出納帳を一冊ずつ読んでいる。顔を上げなかった。上げなかったが、頁をめくる手が、少し前から止まっていた。", "エーリカはそれ以上何も言わず、帳面に目を戻した。今朝から、組合の出納帳を一冊ずつ読んでいる。顔は上げなかった。上げなかったが、頁をめくる手は、さっきから止まったままだった。", "連続性", "取り残された一文の削除と、エーリカの紹介の重複の整理"),
    (9, "とだけ言った。何を読んでいるのかも、なぜ読んでいるのかも、訊かなかった。", "とだけ言った。\n\nアガタは、何を読んでいるのかも、なぜ読んでいるのかも、訊かなかった。", "表現", "「訊かなかった」の主語がエーリカに読めるため、アガタを主語に立てて段落を分ける"),
    (11, "小さい役人は、いつも上と下に挟まれる。隊長も似たようなもんだ」", "小さい役人は、いつも上と下に挟まれる。私も似たようなもんだ」", "表現", "マグダが自分を三人称で「隊長」と呼ぶのは不自然。一人称「私」に"),
    (12, "最後の客を送り出して、椅子を一つずつ卓に上げた。六つあった。", "最後の客を送り出して、六つの卓に、椅子を一つずつ上げた。", "誤字", "六つなのは卓（第一作から）で、椅子ではない"),
    (12, "十日前からは、天井で七歩が鳴っていた。", "十日あまり前からは、天井で七歩が鳴っていた。", "連続性", "着任は霜月二十一日。師走二日の夜までは十一日"),
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
