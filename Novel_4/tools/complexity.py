#!/usr/bin/env python3
"""complexity.py — 企画案（または CANON）の設定・背景の複雑さを計測する。加点はしない計測軸。

  python3 tools/complexity.py measure --tag c1r2 [--judge luna|mimop|qwen] [--timeout 165]
判定規則は compe/complexity_prompt.md。軸と項は本文からの引用が照合に通ったものだけを数え直し、
審判の自己申告（n_axes / n_ending / label）と、照合後に機械で出し直した判定の両方を記録する。
"""
import argparse
import concurrent.futures as cf
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import team  # noqa: E402
from team import CFG, ROOT, rd, wr, sec, chat, parse_json, budget, verified  # noqa: E402

PROMPT = ROOT / "compe" / "complexity_prompt.md"
FIELDS = ("title", "setting", "synopsis", "highlight", "appeal", "must_keep")


def judge_prof(name, timeout):
    if name == "luna":
        p = dict(CFG["evolve"]["judge"])
    else:
        p = dict(CFG["compe"]["judges"][name])
    p["timeout_sec"] = timeout
    return p


def label_of(n_axes, n_end):
    return "シンプル" if 1 <= n_axes <= 3 and n_end <= n_axes else "複雑"


def measure(a):
    b = ROOT / "runs" / "compe" / a.tag
    mp = json.loads(rd(b / "map.json"))
    jp = judge_prof(a.judge, a.timeout)
    od = b / f"complexity_{a.judge}"
    todo = [(pid, p) for pid, p in mp["props"].items() if not (od / f"{pid}.json").exists()]
    for i in range(0, len(todo), 3):
        budget(f"計測{i // 3}", a.limit)

        def one(x):
            pid, p = x
            body = "\n".join(f"- {k}：{p[k]}" for k in FIELDS)
            for _ in range(2):
                try:
                    o = parse_json(chat(jp, "あなたは物語の構造を測る計測係です。JSONだけを返します。", sec("企画案", body) + "\n" + rd(PROMPT), f"complexity:{pid}"))
                    assert isinstance(o.get("axes"), list) and isinstance(o.get("ending_terms"), list) and o.get("label") in ("シンプル", "複雑")
                    wr(od / f"{pid}.json", json.dumps(o, ensure_ascii=False, indent=1))
                    return
                except Exception as e:
                    team.log(ev="complexity_err", pid=pid, err=str(e)[:120])
        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            list(ex.map(one, todo[i:i + 3]))
    rows = []
    for pid, p in mp["props"].items():
        f = od / f"{pid}.json"
        if not f.exists():
            continue
        o = json.loads(rd(f))
        body = " ".join(p[k] for k in FIELDS)
        ax = [x for x in o["axes"] if verified(x.get("quote"), body)]
        en = [x for x in o["ending_terms"] if verified(x.get("quote"), body)]
        rows.append((pid, p, o, len(ax), len(en), sum(1 for x in en if x.get("new")), label_of(len(ax), len(en))))
    L = [f"# 設定・背景の複雑さ（{a.tag}／計測：{jp['model']}）\n", "加点はしない計測軸。規則：元1〜3で結末の項数が元を超えない＝シンプル、元4以上か結末で項が増える＝複雑。数は引用が照合に通った軸・項だけ（括弧内は審判の自己申告）。\n",
         "| id | 作者 | テーマ | 仮タイトル | 元 | 結末の項（うち新規） | 判定 | 審判の判定 | 対立の型 | 軸 |\n|---|---|---|---|---|---|---|---|---|---|"]
    for pid, p, o, na, ne, nn_, lab in rows:
        L.append(f"| {pid} | {p['author']} | {p['theme']} | {p['title']} | {na}（{o.get('n_axes')}） | {ne}（{o.get('n_ending')}）／新{nn_} | {lab} | {o['label']}{'' if o['label'] == lab else ' ⚠'} | {'・'.join(o.get('conflict_types', []))} | {'、'.join(x['name'] for x in o['axes'])} |")
    L.append("\n## 判定の理由（審判の記述）")
    for pid, p, o, *_ in rows:
        L.append(f"- {pid} {p['title']}：{o.get('note', '')}")
    wr(ROOT / "notes" / f"COMPLEXITY_{a.tag}_{a.judge}.md", "\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("measure")
    s.add_argument("--tag", default="c1r2")
    s.add_argument("--judge", default="luna")
    s.add_argument("--timeout", type=int, default=165)
    s.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()
    team.RUN = ROOT / "runs" / "compe" / a.tag
    {"measure": measure}[a.cmd](a)


if __name__ == "__main__":
    main()
