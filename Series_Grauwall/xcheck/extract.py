#!/usr/bin/env python3
"""xcheck/extract.py — 各話の本文から、人物のペルソナ・場所の情景・時と季節の手がかりを JSON で抜き出す（縦の精査の材料）。
  python3 extract.py 01 02 ...   （引数なしなら全話）
出力: xcheck/out/epNN.json と epNN.raw.txt
"""
import json, os, re, sys, time, urllib.request, concurrent.futures as cf
from pathlib import Path
HERE = Path(__file__).resolve().parent; SG = HERE.parent; ROOT = SG.parent
EPS = {"01":"Grauwall_01/output/final.md","02":"Grauwall_02/output/final_proofread.md","03":"Grauwall_03_aion/output/final_proofread.md",
"04":"Grauwall_04/output/final.md","05":"Grauwall_05/output/final.md","06":"Grauwall_06/output/final_proofread.md","07":"Grauwall_07/output/final_proofread.md",
"08":"Grauwall_08/output/final_proofread.md","09":"Grauwall_09/output/final_proofread.md","10":"Grauwall_10/output/final_proofread.md",
"11":"Grauwall_11/output/final_proofread.md","12":"Grauwall_12/output/final.md"}
MODEL = os.environ.get("XCHECK_MODEL", "openai/gpt-6-luna-pro")
def key():
    for line in (ROOT/".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="): return line.split("=",1)[1].strip().strip('"')
    sys.exit("no key")
PROMPT = (HERE/"PROMPT.md").read_text(encoding="utf-8")
def chunks(ep, limit=10000):
    lines = (SG/EPS[ep]).read_text(encoding="utf-8").splitlines()
    out, cur, n = [], [], 0
    for i, l in enumerate(lines):
        if re.match(r"^#{1,2}\s*第", l) and n > limit*0.6:
            out.append(cur); cur, n = [], 0
        if l.strip(): cur.append(f"L{i+1}: {l}"); n += len(l)
        if n > limit: out.append(cur); cur, n = [], 0
    if cur: out.append(cur)
    return ["\n".join(c) for c in out]
def run(job):
    ep, k, numbered = job
    tag = f"ep{ep}_{k:02d}"
    if (HERE/"out"/f"{tag}.json").exists(): return f"{tag} skip"
    msg = PROMPT.replace("{{EP}}", ep).replace("{{SRC}}", EPS[ep]) + "\n\n## 本文（行番号つき）\n" + numbered
    body = {"model": MODEL, "messages": [{"role":"system","content":"あなたは厳格な小説編集者であり記録係です。指定の形式の JSON だけを返します。"},{"role":"user","content":msg}],
            "temperature": 0.1, "max_tokens": 32000, "reasoning": {"effort": "low"}, "response_format": {"type":"json_object"}}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer "+key(), "Content-Type":"application/json", "HTTP-Referer":"https://localhost/xcheck", "X-OpenRouter-Title":"xcheck"})
    for attempt in range(1):
        try:
            t=time.time(); r = json.loads(urllib.request.urlopen(req, timeout=TMO).read())
            txt = r["choices"][0]["message"]["content"]; (HERE/"out").mkdir(exist_ok=True)
            (HERE/"out"/f"{tag}.raw.txt").write_text(txt, encoding="utf-8")
            m = re.search(r"\{.*\}", txt, re.S); data = json.loads(m.group(0))
            (HERE/"out"/f"{tag}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            u = r.get("usage", {}); return f"{tag} ok {time.time()-t:.0f}s in={u.get('prompt_tokens')} out={u.get('completion_tokens')}"
        except Exception as e:
            err = repr(e)[:300]; time.sleep(5)
    return f"{tag} FAILED {err}"
TMO = int(os.environ.get("XCHECK_TIMEOUT", "160"))
if __name__ == "__main__":
    # 引数: 話番号 [チャンク番号...]。--list でチャンク数を表示
    if sys.argv[1] == "--list":
        for ep in EPS: print(ep, len(chunks(ep)), [len(c) for c in chunks(ep)])
        sys.exit()
    ep = sys.argv[1]; cs = chunks(ep); ks = [int(x) for x in sys.argv[2:]] or list(range(1, len(cs)+1))
    jobs = [(ep, k, cs[k-1]) for k in ks]
    with cf.ThreadPoolExecutor(8) as ex:
        for res in ex.map(run, jobs): print(res, flush=True)
