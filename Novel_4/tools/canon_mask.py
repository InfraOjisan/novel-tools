#!/usr/bin/env python3
"""canon_mask.py — CANON の一部を隠して渡したとき、プロットの収束がどこで乱れるかを測る。

  python3 tools/canon_mask.py run N [--levels 0,25,50,75,100] [--samples 4] [--models dsf,mimof,...]   # 生成（再実行で続きから）
  python3 tools/canon_mask.py judge N        # 完全な CANON に照らして違反を数える（主審判 luna）
  python3 tools/canon_mask.py report N       # 収束・違反の表 → notes/CANON_MASK_chNN.md
マスクは CANON の箇条書き行を、行ごとの固定乱数で取り除く（高い率のマスクは低い率のマスクを含む）。モデルにはマスクしたことを伝えない。
"""
import argparse
import concurrent.futures as cf
import itertools
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import team  # noqa: E402
from team import CFG, ROOT, rd, wr, sec, nn, chat, parse_json, verified, log, budget, canon_text, plot_context, norm  # noqa: E402

E = CFG["evolve"]
OUT = ROOT / "runs" / "canonmask"
team.RUN = ROOT / "runs" / "plot"

TASK = """# 依頼
第{N}章のプロット（場面の骨組み）を**1案**作ってください。本文は書きません。
- 場面は2〜4つ。各場面は「場面名／場所と時刻／行為の連鎖（箇条書き4〜8行）」。
- 最後に「結び」を1〜2行。
- 全体で1,400字以内。管理用語（糸・スロット・CANON・LEDGER など）は書かない。
出力はプロット本文のみ。"""

MODELS = {p["name"]: p for p in E["players"]}
MODELS["kimi"] = {"name": "kimi", "provider": "go", "api": "chat", "model": "kimi-k3", "temperature": 1.0, "max_tokens": 6000, "timeout_sec": 140, "extra": {"thinking": {"type": "disabled"}}}

JUDGE_PROMPT = """あなたは公平な審判です。下の「プロット」が、下の CANON（不変条件・数値・時刻・固有名詞・人物・語り・禁止線）に**違反している箇所**を挙げてください。
- 違反＝CANON が定めた事実と食い違う（時刻・数・名前・場所・人物の特徴・世界の法則）、CANON が禁じた事を行う、CANON が許す人数を超えて名前のある人物を出す、など。
- CANON に書かれていない細部を足すだけでは違反ではない。
- 引用は一字一句そのまま写す（照合に通らない指摘は捨てられる）。
出力はJSONのみ：{"violations":[{"canon_quote":"CANON から写した30字以内","plot_quote":"プロットから写した30字以内","why":"40字以内"}]}。なければ {"violations":[]}。"""


MODELS["glm52"] = {"name": "glm52", "provider": "openrouter", "api": "chat", "model": "z-ai/glm-5.2", "temperature": 1.0, "max_tokens": 6000, "timeout_sec": 140, "reasoning": {"enabled": False}}
MODELS["aion"] = dict(CFG["aion"], name="aion", reasoning={"effort": "low"}, max_tokens=12000, timeout_sec=170, temperature=0.8)


def clean(t):
    return re.sub(r"[*_`#]", "", t)


def bullets(canon):
    return [i for i, l in enumerate(canon.splitlines()) if re.match(r"^\s*-\s", l)]


def keys(canon):
    r = random.Random("canon-mask-v1")
    return {i: r.random() for i in bullets(canon)}


def masked_canon(canon, pct):
    ks = keys(canon)
    ls = canon.splitlines()
    gone = {i for i, k in ks.items() if k < pct / 100}
    return "\n".join(l for i, l in enumerate(ls) if i not in gone), gone


def gen(a):
    n = int(a.n)
    team.guard_stop()
    canon = canon_text()
    levels = [int(x) for x in a.levels.split(",")]
    names = a.models.split(",")
    jobs = []
    for pct in levels:
        mc, _ = masked_canon(canon, pct)
        ctx = plot_context(n, mc)
        for nm in names:
            for k in range(a.samples):
                jobs.append((OUT / f"ch{nn(n)}" / "gen" / f"{nm}__L{pct}__{k}.md", MODELS[nm], "あなたは小説の構成作家です。", ctx + "\n" + TASK.replace("{N}", str(n))))
    todo = [j for j in jobs if not j[0].exists()]
    for i in range(0, len(todo), 12):
        batch = todo[i:i + 12]
        budget(f"生成{i // 12}", a.limit)

        def one(j):
            f, prof, sy, pr = j
            for _ in range(2):
                try:
                    o = chat(prof, sy, pr, f"canonmask:{prof['name']}")
                    if len(o.strip()) >= 300:
                        wr(f, o.strip() + "\n")
                        return None
                except Exception as e:
                    last = str(e)[:100]
            return f"{prof['name']}: {last if 'last' in dir() else '短すぎ'}"
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            errs = [e for e in ex.map(one, batch) if e]
        if errs:
            log(ev="canonmask_gen_err", errs=errs)
    print(f"生成 {sum(1 for j in jobs if j[0].exists())}/{len(jobs)}")


def judge(a):
    n = int(a.n)
    canon = canon_text()
    gd = OUT / f"ch{nn(n)}" / "gen"
    jd = OUT / f"ch{nn(n)}" / "judge"
    jp = dict(E["judge"], timeout_sec=120)
    todo = [f for f in sorted(gd.glob("*.md")) if not (jd / (f.stem + ".json")).exists()]
    for i in range(0, len(todo), 12):
        batch = todo[i:i + 12]
        budget(f"審判{i // 12}", a.limit)

        def one(f):
            for _ in range(2):
                try:
                    o = parse_json(chat(jp, "あなたは公平な審判です。JSONだけを返します。", sec("CANON", canon) + sec("プロット", rd(f)) + "\n" + JUDGE_PROMPT, "canonmask:judge"))
                    assert isinstance(o.get("violations"), list)
                    wr(jd / (f.stem + ".json"), json.dumps(o, ensure_ascii=False, indent=1))
                    return
                except Exception:
                    pass
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            list(ex.map(one, batch))
    print(f"審判 {len(list(jd.glob('*.json')))}/{len(list(gd.glob('*.md')))}")


def bg(t):
    t = re.sub(r"\s+", "", t)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def jac(x, y):
    return len(x & y) / max(1, len(x | y))


def report(a):
    n = int(a.n)
    canon = canon_text()
    cl = canon.splitlines()
    ks = keys(canon)
    gd = OUT / f"ch{nn(n)}" / "gen"
    jd = OUT / f"ch{nn(n)}" / "judge"
    recs = []
    for f in sorted(gd.glob("*.md")):
        nm, lv, k = f.stem.split("__")
        pct = int(lv[1:])
        txt = rd(f)
        vs = []
        jf = jd / (f.stem + ".json")
        if jf.exists():
            for v in json.loads(rd(jf))["violations"]:
                if verified(v.get("canon_quote"), canon) and verified(clean(v.get("plot_quote") or ""), clean(txt)):
                    q = norm(v["canon_quote"])
                    hit = [i for i in ks if q in norm(cl[i])]
                    masked = bool(hit) and ks[hit[0]] < pct / 100
                    vs.append({"masked": masked, "inbullet": bool(hit)})
        recs.append({"nm": nm, "pct": pct, "k": int(k), "bg": bg(txt), "len": len(txt), "judged": jf.exists(), "v": vs})
    levels = sorted({r["pct"] for r in recs})
    models = sorted({r["nm"] for r in recs})
    mean = lambda v: round(sum(v) / len(v), 3) if v else None
    L = [f"# CANON マスク実験（第{n}章／生成 {len(recs)} 本／レベル {levels}%／モデル {models}）\n",
         "CANON の箇条書きを指定の割合だけ取り除いて渡し、同じ依頼でプロットを複数回作らせた。マスクしたことはモデルに伝えていない。類似度は文字2-gram の Jaccard（高い＝収束）。違反は完全な CANON に照らして luna が数えた（引用の照合に通ったものだけ）。\n"]
    L.append("## レベル別\n| マスク率 | 本数 | 同モデル内の類似度 | 別モデル間の類似度 | L0（完全CANON）の案との類似度 | 違反/本 | うち隠した行への違反/本 | うち隠していない行への違反/本 | 平均字数 |\n|---|---|---|---|---|---|---|---|---|")
    l0 = [r for r in recs if r["pct"] == 0]
    for pct in levels:
        rs = [r for r in recs if r["pct"] == pct]
        within = [jac(x["bg"], y["bg"]) for x, y in itertools.combinations(rs, 2) if x["nm"] == y["nm"]]
        cross = [jac(x["bg"], y["bg"]) for x, y in itertools.combinations(rs, 2) if x["nm"] != y["nm"]]
        to0 = [jac(x["bg"], y["bg"]) for x in rs for y in l0 if x is not y]
        jr = [r for r in rs if r["judged"]]
        vm = [sum(1 for v in r["v"] if v["masked"]) for r in jr]
        vu = [sum(1 for v in r["v"] if not v["masked"]) for r in jr]
        L.append(f"| {pct}% | {len(rs)} | {mean(within)} | {mean(cross)} | {mean(to0)} | {mean([a + b for a, b in zip(vm, vu)])} | {mean(vm)} | {mean(vu)} | {int(mean([r['len'] for r in rs]))} |")
    L.append("\n## モデル別（同モデル内の類似度／違反/本）\n| モデル | " + " | ".join(f"{p}%" for p in levels) + " |\n|---|" + "---|" * len(levels))
    for nm in models:
        cells = []
        for pct in levels:
            rs = [r for r in recs if r["nm"] == nm and r["pct"] == pct]
            within = [jac(x["bg"], y["bg"]) for x, y in itertools.combinations(rs, 2)]
            jr = [r for r in rs if r["judged"]]
            cells.append(f"{mean(within)}／{mean([len(r['v']) for r in jr])}")
        L.append(f"| {nm} | " + " | ".join(cells) + " |")
    wr(ROOT / "notes" / f"CANON_MASK_ch{nn(n)}.md", "\n".join(L) + "\n")
    print("\n".join(L))


# ---------------------------------------------------------------- 逸脱の指示（人が範囲を決めて外させる）
DIRECTIVES = {
    "D1": {"axis": "自然法則（時刻）", "target": "小運河の浅瀬が最も浅くなるのは04:10前後（大運河の水位はすでに上がっている）",
           "how": "この章に限り、小運河の浅瀬が最も浅くなる時刻を02:40に前倒ししてよい。大運河がまだ上がっていない時刻に、底の見える小運河へネリが入る場面を一つ作る。",
           "scope": "この時刻の変更と、それに直接かかわる場面1つだけ。他の時刻・数値・人物・語りは CANON のまま。"},
    "D2": {"axis": "人物数", "target": "名前のある人物はネリを含めて四人まで",
           "how": "この章に限り、五人目の名前のある人物を一人だけ出してよい。名前と立場は自由。",
           "scope": "その一人の登場場面だけ。ほかの三人の設定・人数の扱い・時刻・語りは CANON のまま。"},
    "D3": {"axis": "視点", "target": "視点はネリ・ソルダートの三人称限定。彼女の知覚・記憶・判断の外は書かない",
           "how": "この章に限り、1つの場面の中の数行だけ、ネリが見聞きできない別の場所の出来事を地の文で書いてよい。",
           "scope": "その数行だけ。ほかの場面は三人称限定のまま。人称・時制（過去形）・時刻・人物は CANON のまま。"},
}

DEV_TASK = """# 逸脱の指示（人が出す）
今回のプロットでは、CANON の次の一条を、人が指定した範囲でだけ外してよい。
- 外してよい条：{target}
- どう外すか：{how}
- 影響範囲：{scope}
**範囲の外では CANON を守る。** 外し方は、物語が面白くなる具体的な行為で書く。

# 依頼
第{N}章のプロット（場面の骨組み）を**1案**作ってください。本文は書きません。
- 場面は2〜4つ。各場面は「場面名／場所と時刻／行為の連鎖（箇条書き4〜8行）」。最後に「結び」を1〜2行。
- 全体で1,400字以内（逸脱メモを除く）。管理用語は書かない。
- 末尾に「逸脱メモ」を書く：(1) どこでどう外したか (2) 外したために他の場面で変えたこと (3) 影響範囲の外には出していないこと。
出力はプロット本文と逸脱メモのみ。"""

DEV_JUDGE = """あなたは公平な審判です。人が出した「逸脱の指示」と、下の「プロット」を見て答えてください。CANON は、指示で外してよいとされた一条を除いて守られるべきものです。
1. implemented：指示された逸脱を、プロットの中で実際に行っているか（true/false）。行っていれば implemented_quote にプロットから一字一句そのまま30字以内で写す。
2. other_violations：**指示で許された逸脱を除いて**、プロットが CANON に違反している箇所（時刻・数・名前・人物の特徴・世界の法則・語りなど）。許された範囲を越えた逸脱（範囲の外へ広がったもの）も含める。引用は一字一句そのまま（canon_quote は CANON から、plot_quote はプロットから、各30字以内）。
3. memo：プロット末尾に逸脱メモがあるか（present）、メモの内容が実際のプロットと食い違っていないか（accurate）。
出力はJSONのみ：{"implemented":true,"implemented_quote":"","other_violations":[{"canon_quote":"","plot_quote":"","why":"40字以内"}],"memo":{"present":true,"accurate":true}}"""


def dev_gen(a):
    n = int(a.n)
    team.guard_stop()
    canon = canon_text()
    ctx = plot_context(n, canon)
    jobs = []
    for dk, d in DIRECTIVES.items():
        for nm in a.models.split(","):
            for k in range(a.samples):
                jobs.append((OUT / f"ch{nn(n)}" / "dev" / "gen" / f"{nm}__{dk}__{k}.md", MODELS[nm], "あなたは小説の構成作家です。",
                             ctx + "\n" + DEV_TASK.format(N=n, **d)))
    todo = [j for j in jobs if not j[0].exists()]
    for i in range(0, len(todo), 12):
        batch = todo[i:i + 12]
        budget(f"逸脱生成{i // 12}", a.limit)

        def one(j):
            f, prof, sy, pr = j
            for _ in range(2):
                try:
                    o = chat(prof, sy, pr, f"canonmask:dev:{prof['name']}")
                    if len(o.strip()) >= 300:
                        wr(f, o.strip() + "\n")
                        return
                except Exception:
                    pass
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            list(ex.map(one, batch))
    print(f"逸脱生成 {sum(1 for j in jobs if j[0].exists())}/{len(jobs)}")


def dev_judge(a):
    n = int(a.n)
    canon = canon_text()
    gd = OUT / f"ch{nn(n)}" / "dev" / "gen"
    jd = OUT / f"ch{nn(n)}" / "dev" / "judge"
    jp = dict(E["judge"], timeout_sec=120)
    todo = [f for f in sorted(gd.glob("*.md")) if not (jd / (f.stem + ".json")).exists()]
    for i in range(0, len(todo), 12):
        batch = todo[i:i + 12]
        budget(f"逸脱審判{i // 12}", a.limit)

        def one(f):
            d = DIRECTIVES[f.stem.split("__")[1]]
            dtext = f"外してよい条：{d['target']}\nどう外すか：{d['how']}\n影響範囲：{d['scope']}"
            for _ in range(2):
                try:
                    o = parse_json(chat(jp, "あなたは公平な審判です。JSONだけを返します。", sec("CANON", canon) + sec("逸脱の指示", dtext) + sec("プロット", rd(f)) + "\n" + DEV_JUDGE, "canonmask:devjudge"))
                    assert "implemented" in o and isinstance(o.get("other_violations"), list)
                    wr(jd / (f.stem + ".json"), json.dumps(o, ensure_ascii=False, indent=1))
                    return
                except Exception:
                    pass
        with cf.ThreadPoolExecutor(max_workers=12) as ex:
            list(ex.map(one, batch))
    print(f"逸脱審判 {len(list(jd.glob('*.json')))}/{len(list(gd.glob('*.md')))}")


def dev_report(a):
    n = int(a.n)
    canon = canon_text()
    gd = OUT / f"ch{nn(n)}" / "dev" / "gen"
    jd = OUT / f"ch{nn(n)}" / "dev" / "judge"
    allbase = [bg(rd(f)) for f in (OUT / f"ch{nn(n)}" / "gen").glob("*__L0__*.md")]
    recs = []
    for f in sorted(gd.glob("*.md")):
        nm, dk, k = f.stem.split("__")
        txt = rd(f)
        r = {"nm": nm, "dk": dk, "bg": bg(txt.split("逸脱メモ")[0]), "judged": False}
        jf = jd / (f.stem + ".json")
        if jf.exists():
            o = json.loads(rd(jf))
            m = o.get("memo") or {}
            r.update(judged=True, impl=bool(o.get("implemented")) and verified(clean(o.get("implemented_quote") or ""), clean(txt)),
                     other=sum(1 for v in o["other_violations"] if verified(v.get("canon_quote"), canon) and verified(clean(v.get("plot_quote") or ""), clean(txt))),
                     memo_ok=bool(m.get("present")) and bool(m.get("accurate")), memo_only=bool(m.get("present")) and not bool(o.get("implemented")))
        recs.append(r)
    mean = lambda v: round(sum(v) / len(v), 3) if v else None
    bb = [jac(x, y) for x, y in itertools.combinations(allbase, 2)]
    L = [f"# 逸脱の指示の実験（第{n}章／{len(recs)} 本／指示 {sorted(DIRECTIVES)}）\n",
         "人が「どの条を・どう外し・どの範囲まで」と具体的に指示したとき、モデルが（1）実際に外すか、（2）範囲を守るか、（3）出力が収束から外れるか。\n",
         "- 実施率＝指示の逸脱をプロットで実際に行った割合（引用が照合に通ったもの）",
         "- 範囲外の違反/本＝指示で許された逸脱を除く CANON 違反（基準：指示なしの 0% マスクで 0.4 件/本前後）",
         "- メモ正確＝逸脱メモがあり内容が食い違わない割合",
         "- L0 との類似度＝指示なしのプロット（全モデル）との文字2-gram Jaccard（低い＝外れた）\n",
         "## 指示別\n| 指示 | 外す条 | 本数 | 実施率 | 範囲外の違反/本 | メモ正確 | L0との類似度 | 別モデル間の類似度 |\n|---|---|---|---|---|---|---|---|"]
    for dk, d in DIRECTIVES.items():
        rs = [r for r in recs if r["dk"] == dk]
        jr = [r for r in rs if r["judged"]]
        cross = [jac(x["bg"], y["bg"]) for x, y in itertools.combinations(rs, 2) if x["nm"] != y["nm"]]
        to0 = [jac(x["bg"], b) for x in rs for b in allbase]
        L.append(f"| {dk} | {d['axis']} | {len(rs)} | {mean([1 if r['impl'] else 0 for r in jr])} | {mean([r['other'] for r in jr])} | {mean([1 if r['memo_ok'] else 0 for r in jr])} | {mean(to0)} | {mean(cross)} |")
    L.append(f"\n（参考：指示なし L0 同士の類似度 {mean(bb)}）")
    models = sorted({r["nm"] for r in recs})
    L.append("\n## モデル別（実施率／範囲外の違反/本／メモ正確／メモだけで実体なし）\n| モデル | " + " | ".join(DIRECTIVES) + " | 全体 |\n|---|" + "---|" * (len(DIRECTIVES) + 1))
    for nm in models:
        cells = []
        for sel in list(DIRECTIVES) + [None]:
            jr = [r for r in recs if r["nm"] == nm and (sel is None or r["dk"] == sel) and r["judged"]]
            cells.append(f"{mean([1 if r['impl'] else 0 for r in jr])}／{mean([r['other'] for r in jr])}／{mean([1 if r['memo_ok'] else 0 for r in jr])}／{mean([1 if r['memo_only'] else 0 for r in jr])}")
        L.append(f"| {nm} | " + " | ".join(cells) + " |")
    wr(ROOT / "notes" / f"CANON_DEVIATE_ch{nn(n)}.md", "\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("run", "judge", "report", "dev-run", "dev-judge", "dev-report"):
        s = sp.add_parser(c)
        s.add_argument("n")
        s.add_argument("--levels", default="0,25,50,75,100")
        s.add_argument("--samples", type=int, default=4)
        s.add_argument("--models", default="dsf,mimof,lc,dsp,muse,kimi,glm52,aion")
        s.add_argument("--limit", type=int, default=140)
    a = ap.parse_args()
    {"run": gen, "judge": judge, "report": report, "dev-run": dev_gen, "dev-judge": dev_judge, "dev-report": dev_report}[a.cmd](a)


if __name__ == "__main__":
    main()
