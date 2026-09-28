#!/usr/bin/env python3
"""fairness — ミステリとして読者に公正かを、HermesAgent（または任意の判定モデル）に判定させる。

二種類の判定を行う。
  1. 読者役の推理（solve）: 第N章までの本文「だけ」を渡し、その時点の推理を答えさせる。
     第1〜2章で当たりすぎていれば「早すぎる看破」、第5章で当たらなければ「解けない」疑い。
  2. 公正監査（audit）: 真相台帳（CANON）と全章の本文を渡し、語りの嘘・作法違反・後出し証拠がないかを審判させる。

  python3 tools/fairness.py packets          判定用パケットを work/fair/ に作る
  python3 tools/fairness.py status           答えがそろっているかを表示
  python3 tools/fairness.py run --api        judge プロファイル（config.json の llm.profiles.judge）で全パケットを API 判定
  python3 tools/fairness.py report           答えを集計して output/fairness_report.md を作る

HermesAgent が自分で判定するとき（推奨）:
  - work/fair/fair_solve_chNN.packet.md を **一つずつ、毎回まっさらな会話（新しいセッションかサブエージェント）で** 読み、
    答えのJSONを work/fair/fair_solve_chNN.answer.json に保存する。solve の途中で canon/・state/・他章のファイルを開かないこと。
  - solve がすべて終わってから work/fair/fair_audit.packet.md を読み、答えを work/fair/fair_audit.answer.json に保存する。
  - 最後に report を実行する。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
N_CH = CFG["chapters"]
FAIR = ROOT / "work" / "fair"
SOLVE_CH = CFG.get("fairness", {}).get("solve_chapters", list(range(1, N_CH - 1)))
FIELDS = [("thief", "KEY_THIEF", "盗んだ者"), ("mastermind", "KEY_MASTERMIND", "仕組んだ者"),
          ("jewel_mover", "KEY_JEWEL_MOVER", "隠し場所から持ち出した者"), ("jewel_keeper", "KEY_JEWEL_KEEPER", "宝石を預かった者"),
          ("assistant_true", "KEY_ASSISTANT_TRUE", "助手の正体")]


def rd(p):
    return Path(p).read_text(encoding="utf-8")


def nn(n):
    return f"{n:02d}"


def sec(title, body):
    return f"\n\n<資料 名前=\"{title}\">\n{body.strip()}\n</資料>\n"


def chapters_text(upto):
    out = []
    for i in range(1, upto + 1):
        f = ROOT / "chapters" / f"ch{nn(i)}.md"
        if not f.exists():
            sys.exit(f"chapters/ch{nn(i)}.md がありません。全章が確定してから実行してください。")
        out.append(rd(f).strip())
    return "\n\n".join(out)


def title():
    m = re.search(r"タイトル：\s*(.+)", rd(ROOT / "canon" / "CANON.md"))
    return m.group(1).strip() if m else "無題"


def keys():
    text = rd(ROOT / "canon" / "CANON.md")
    # 値の（ ）内は説明なので照合から外す。「|」で別名を並べられる（例：兎人|兎族|兎）
    return {k: re.sub(r"[（(][^）)]*[）)]", "", v).strip() for k, v in re.findall(r"(KEY_[A-Z_]+)\s*[：:]\s*(.+)", text)}


def packets():
    FAIR.mkdir(parents=True, exist_ok=True)
    made = []
    for n in SOLVE_CH:
        s = f"<!-- TASK: fair-solve CH={nn(n)} -->\nこれは一回きりの依頼です。ツールやファイル操作は使わず、指定された形式のJSONだけを返答してください。"
        s += sec(f"本文（『{title()}』第1章〜第{n}章）", chapters_text(n))
        s += sec("依頼", rd(ROOT / "prompts" / "fair_solve.md").replace("{{N}}", str(n)))
        p = FAIR / f"fair_solve_ch{nn(n)}.packet.md"
        p.write_text(s, encoding="utf-8")
        made.append(p)
    s = "<!-- TASK: fair-audit -->\nこれは一回きりの依頼です。ツールやファイル操作は使わず、指定された形式のJSONだけを返答してください。"
    s += sec("作者の設定書と真相台帳（CANON）", rd(ROOT / "canon" / "CANON.md"))
    s += sec(f"全章の本文（『{title()}』）", chapters_text(N_CH))
    s += sec("依頼", rd(ROOT / "prompts" / "fair_audit.md"))
    p = FAIR / "fair_audit.packet.md"
    p.write_text(s, encoding="utf-8")
    made.append(p)
    for p in made:
        print(f"{p.relative_to(ROOT)}  ({len(rd(p))}字)")
    print("答えは同じ名前で .packet.md → .answer.json にして work/fair/ に置く（solve は毎回まっさらな会話で）。")


def names():
    return [f"fair_solve_ch{nn(n)}" for n in SOLVE_CH] + ["fair_audit"]


def status():
    for k in names():
        a = FAIR / f"{k}.answer.json"
        print(f"{'✓' if a.exists() else '·'} {k}")


def extract_json(raw):
    raw = re.sub(r"```(?:json)?", "", raw)
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j < 0:
        return None
    try:
        return json.loads(raw[i:j + 1])
    except json.JSONDecodeError:
        return None


def run_api():
    cmd = CFG.get("fairness", {}).get("judge_cmd", ["python3", "tools/call_llm.py", "{packet}", "judge"])
    for k in names():
        a = FAIR / f"{k}.answer.json"
        if a.exists():
            print(f"{k}: 回答済み（やり直すなら answer.json を消す）")
            continue
        pk = FAIR / f"{k}.packet.md"
        if not pk.exists():
            sys.exit("先に packets を実行してください。")
        r = subprocess.run([c.replace("{packet}", str(pk)) for c in cmd], cwd=ROOT, capture_output=True, text=True)
        (FAIR / f"{k}.out").write_text(r.stdout, encoding="utf-8")
        j = extract_json(r.stdout)
        if r.returncode != 0 or j is None:
            print(f"{k}: 失敗（{r.returncode}） {r.stderr[-300:]}")
            continue
        a.write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{k}: 回答を保存")


def hit(guess, truth):
    if not guess or not truth or guess in ("不明", "?"):
        return False
    parts = [t for t in re.split(r"[、,，・/／|｜\s]+", truth) if t]
    return any(t in guess or guess in t for t in parts)


def report():
    k = keys()
    if not k:
        sys.exit("CANON に解答キー（KEY_...：値）がありません。")
    lines = [f"# 公正判定レポート『{title()}』", "", "## 読者役の推理（章ごと）", "",
             "| 章 | " + " | ".join(f[2] for f in FIELDS) + " | 嘘つき | 「僕」二人 | 自信 |",
             "|---|" + "---|" * (len(FIELDS) + 3)]
    solved_at, early, notes = None, [], []
    liars_true = [x for x in re.split(r"[、,，\s]+", k.get("KEY_LIARS", "")) if x]
    for n in SOLVE_CH:
        a = FAIR / f"fair_solve_ch{nn(n)}.answer.json"
        if not a.exists():
            lines.append(f"| {n} | " + " | ".join("（未回答）" for _ in FIELDS) + " | | | |")
            continue
        j = json.loads(rd(a))
        cells = []
        score = 0
        for key, kk, _ in FIELDS:
            ok = hit(str(j.get(key, "")), k.get(kk, ""))
            score += ok
            cells.append(("○ " if ok else "× ") + str(j.get(key, ""))[:18])
        guessed = " ".join(j.get("liars", []) if isinstance(j.get("liars"), list) else [str(j.get("liars", ""))])
        lh = sum(1 for t in liars_true if t in guessed)
        tn = str(j.get("two_narrators", ""))
        two_ok = all(t in tn for t in re.split(r"[、,，\s]+", k.get("KEY_TWO_NARRATORS", "")) if t)
        conf = int(j.get("confidence", 0) or 0)
        lines.append(f"| {n} | " + " | ".join(cells) + f" | {lh}/{len(liars_true)} | {'○' if two_ok else '×'} | {conf} |")
        core = hit(str(j.get("thief", "")), k.get("KEY_THIEF", "")) and hit(str(j.get("mastermind", "")), k.get("KEY_MASTERMIND", ""))
        if core and solved_at is None:
            solved_at = n
        if n <= 2 and core and conf >= 70:
            early.append(n)
        if j.get("unfair_feeling"):
            notes.append(f"- 第{n}章時点の読者の不満: {j['unfair_feeling']}")
    last = SOLVE_CH[-1] if SOLVE_CH else None
    lines += ["", "## 判定", ""]
    lines.append(f"- 盗んだ者と仕組んだ者を最初に当てた章: {('第%d章' % solved_at) if solved_at else '当てられなかった'}")
    lines.append(f"- 早すぎる看破（第2章までに自信70以上で的中）: {'あり（第' + '・'.join(map(str, early)) + '章）' if early else 'なし'}")
    if last and not (FAIR / f"fair_solve_ch{nn(last)}.answer.json").exists():
        lines.append("- 第5章時点の推理: 未回答")
    a = FAIR / "fair_audit.answer.json"
    if a.exists():
        j = json.loads(rd(a))
        high = [i for i in j.get("issues", []) if i.get("severity") == "high"]
        lines += [f"- 公正監査: {'公正' if j.get('fair') and not high else '要修正'}（score {j.get('score')}、第5章までで解ける: {j.get('solvable_by_ch5')}）",
                  f"- 講評: {j.get('summary', '')}", "", "## 監査の指摘", ""]
        lines += [f"- [{i.get('severity')}] 第{i.get('chapter')}章 {i.get('type')}: {i.get('detail')} → {i.get('fix')}" for i in j.get("issues", [])] or ["- なし"]
    else:
        lines.append("- 公正監査: 未回答")
    if notes:
        lines += ["", "## 読者役の声", ""] + notes
    lines += ["", "## 解答キー（CANON 第11節）", ""] + [f"- {kk}：{v}" for kk, v in k.items()]
    out = ROOT / "output" / "fairness_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)} を作成")


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "packets":
        packets()
    elif a[0] == "status":
        status()
    elif a[0] == "run":
        if "--api" not in a:
            sys.exit("run は --api のときだけ使う。HermesAgent が自分で判定するときは docstring の手順に従う。")
        run_api()
    elif a[0] == "report":
        report()
    else:
        sys.exit(f"不明なコマンド: {a[0]}")


if __name__ == "__main__":
    main(sys.argv[1:])
