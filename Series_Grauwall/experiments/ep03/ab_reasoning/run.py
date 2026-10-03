#!/usr/bin/env python3
"""Aion 3.5 mini の「推論」の量を変えると、時間・費用・文章がどう変わるかを測る（第3回の本番とは別の場所で行う）。

使い方（novel-tools のどこからでも）:
  python3 Series_Grauwall/experiments/ep03/ab_reasoning/run.py            # 全条件 × 2回を並列で
  python3 Series_Grauwall/experiments/ep03/ab_reasoning/run.py --n 1      # 各1回

- 依頼文は、第10章の「最初の稿」と同じ形のものを novelctl の build_packet で作り直す
  （本番の work/ のファイルは読むだけで、書き換えない）。
- 条件ごとに call_llm.run を別プロセスで呼び、結果を out/ に置く。
- 最後に results.json と、条件を伏せた読み比べ用の blind/ を作る（対応表は key.json）。
"""
import json, os, random, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[2] / "Grauwall_03_aion"          # Series_Grauwall/Grauwall_03_aion
TOOLS = WORK / "tools"
OUT = HERE / "out"
CH = 10

# 条件：reasoning に渡す値（None は reasoning を送らない＝モデルの既定）
CONDS = {
    "high":    {"effort": "high"},          # 本番の書き手と同じ
    "low":     {"effort": "low"},
    "cap4k":   {"max_tokens": 4000},
    "off":     {"enabled": False},           # 推論を切る指定（受け付けるか自体も確かめる）
    "default": None,
}


def build_packet():
    sys.path.insert(0, str(TOOLS))
    os.chdir(WORK)
    import novelctl as nc
    orig_P = nc.P
    pk = OUT / f"write_ch{CH:02d}.packet.md"

    def P(*parts):
        name = parts[-1]
        if name == f"ch{CH:02d}_draft.md" or name == f"ch{CH:02d}_feedback.md":
            return OUT / "_none_" / name          # 存在しない → 「最初の稿」の依頼になる
        if name == f"write_ch{CH:02d}.packet.md":
            return pk                              # 本番の work/ に書かない
        return orig_P(*parts)
    nc.P = P
    nc.log = lambda *a, **k: None                  # 本番の run.log に書かない
    path = nc.build_packet("write", CH)
    return Path(path)


def one(cond, k, packet):
    """子プロセス：1条件1回。"""
    sys.path.insert(0, str(TOOLS))
    os.chdir(WORK)
    import call_llm as c
    orig = c.build_body

    def build_body(role, task, text):
        b = orig(role, task, text)
        b.pop("reasoning", None)
        if CONDS[cond] is not None:
            b["reasoning"] = CONDS[cond]
        return b
    c.build_body = build_body
    prog = OUT / f"{cond}_{k}.progress.json"
    t0 = time.time()
    try:
        content = c.run("writer", "write", packet.read_text(encoding="utf-8"), str(prog))
        ok = True
    except SystemExit:
        content, ok = "", False
    (OUT / f"{cond}_{k}.md").write_text(content, encoding="utf-8")
    p = json.loads(prog.read_text(encoding="utf-8")) if prog.exists() else {}
    (OUT / f"{cond}_{k}.meta.json").write_text(json.dumps(
        {"cond": cond, "k": k, "ok": ok, "sec": round(time.time() - t0),
         "reasoning_chars": p.get("reasoning_chars"), "content_chars": len(content)},
        ensure_ascii=False), encoding="utf-8")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--one":
        return one(sys.argv[2], int(sys.argv[3]), Path(sys.argv[4]))
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 2
    OUT.mkdir(parents=True, exist_ok=True)
    packet = build_packet()
    print(f"依頼文: {packet}（{len(packet.read_text(encoding='utf-8'))}字）")
    procs = []
    for cond in CONDS:
        for k in range(1, n + 1):
            err = open(OUT / f"{cond}_{k}.stderr", "w")
            procs.append((cond, k, subprocess.Popen(
                [sys.executable, __file__, "--one", cond, str(k), str(packet)], stderr=err, stdout=err)))
    print(f"{len(procs)} 本を並列で実行中…（推論が長い条件は数分かかります）")
    t0 = time.time()
    for cond, k, p in procs:
        p.wait()
        print(f"  {cond}_{k} 終了（{time.time() - t0:.0f}秒）")
    # 集計
    res = []
    for cond, k, _ in procs:
        m = json.loads((OUT / f"{cond}_{k}.meta.json").read_text(encoding="utf-8"))
        st = (OUT / f"{cond}_{k}.stderr").read_text(encoding="utf-8")
        for line in st.splitlines():
            if line.startswith("usage:"):
                m["usage"] = line
        m["stderr_tail"] = st.strip().splitlines()[-3:] if st.strip() else []
        res.append(m)
    (HERE / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    # 読み比べ用（条件を伏せる）
    bl = HERE / "blind"
    bl.mkdir(exist_ok=True)
    items = [r for r in res if r["ok"] and r["content_chars"] > 500]
    random.shuffle(items)
    key = {}
    for i, r in enumerate(items, 1):
        name = f"sample_{i:02d}.md"
        (bl / name).write_text((OUT / f"{r['cond']}_{r['k']}.md").read_text(encoding="utf-8"), encoding="utf-8")
        key[name] = f"{r['cond']}_{r['k']}"
    (HERE / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print("完了: results.json / blind/ / key.json")
    for r in res:
        print(f"  {r['cond']:8s} #{r['k']}  ok={r['ok']}  {r['sec']:4d}秒  推論{r.get('reasoning_chars')}字  本文{r['content_chars']}字  {r.get('usage', '')[-60:]}")


if __name__ == "__main__":
    main()
