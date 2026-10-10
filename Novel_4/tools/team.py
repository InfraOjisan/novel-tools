#!/usr/bin/env python3
"""team.py — 星型チーム。司令塔（Claude）が 1 コマンドずつ回す。ワーカーは道具もメモリも持たない 1 回きりの API 呼び出し。

  python3 tools/team.py ping                          各モデルの疎通
  python3 tools/team.py canon                         設計役が CANON 案を作る（canon/CANON.draft.md）
  python3 tools/team.py approve-canon --sha 先頭8字   人の承認後に CANON を確定・固定（変更検知つき）
  python3 tools/team.py write N [--mode team|aion]    第N章（team=複数モデル並列→匿名編集→出典つき検査 / aion=Aion単独→同じ検査）
  python3 tools/team.py judge N                       team と aion の第N章を、名前を伏せて比べる（引用は機械照合）
  python3 tools/team.py status

統制：STOP ファイル（このフォルダ直下）があれば全員止まる。各モードは runs/<mode>/ の中だけを読み書きし、互いを読まない。
出典つき：LLM の指摘・採用理由・台帳の事実は「本文からそのまま写した引用」が機械照合に通ったものだけ採る。
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import sys
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
CH = CFG["chars"]
RUN = ROOT / "runs" / "team"
BANNED = [(re.compile(p), w) for p, w in CFG["banned"]]
RETRY_HTTP = (408, 409, 425, 429, 500, 502, 503, 504)
_CORPUS = None
T0 = time.time()


class ApiError(Exception):
    pass


def nn(n):
    return f"{int(n):02d}"


def rd(p):
    p = Path(p)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def wr(p, s):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def norm(s):
    return re.sub(r"\s+", "", s)


def between(text, a, b):
    i, j = text.find(a), text.find(b)
    return text[i + len(a):j].strip() if i >= 0 and j > i else ""


def sec(title, body):
    return f"\n## {title}\n\n{body.strip()}\n"


def guard_stop():
    s = ROOT / "STOP"
    if s.exists():
        print("STOP: " + rd(s).strip()[:200], file=sys.stderr)
        sys.exit(2)


def log(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    p = RUN / "logs" / "run.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- API
def env_value(names):
    if isinstance(names, str):
        names = [names]
    for n in names:
        if os.environ.get(n):
            return os.environ[n].strip()
    for env in (ROOT / ".env.local", ROOT / ".env", ROOT.parent / ".env.local", ROOT.parent / ".env", ROOT.parent.parent / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                k, _, v = line.strip().partition("=")
                if k.strip().removeprefix("export ").strip() in names and v.strip():
                    return v.strip().strip('"').strip("'")
    return None


SESSION = str(uuid.uuid4())


def resolve(prof):
    p = CFG["providers"][prof.get("provider", "openrouter")]
    url = (p.get("url") or env_value(p["url_env"]) or "").rstrip("/")
    key = env_value(p["key_env"])
    m = env_value(prof["model_env"]) if prof.get("model_env") else prof["model"]
    pre = p.get("strip_prefix")
    if pre and m and m.startswith(pre + "/"):
        m = m[len(pre) + 1:]
    return p, url, key, m


def chat(prof, system, user, task, json_mode=False):
    p, url, key, model = resolve(prof)
    if not key or not url or not model:
        raise ApiError(f"{prof.get('provider')} の URL・キー・モデル名が .env.local にない")
    api = prof.get("api", "chat")
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json",
               "User-Agent": p.get("user_agent", "novel-team/1.0")}
    if p.get("session_header"):
        headers[p["session_header"]] = SESSION
    if api == "messages":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        endpoint = "/messages"
        body = {"model": model, "max_tokens": prof.get("max_tokens", 16000), "temperature": prof.get("temperature", 0.7),
                "system": system, "messages": [{"role": "user", "content": user}]}
    elif api == "responses":
        endpoint = "/responses"
        body = {"model": model, "instructions": system, "input": user, "max_output_tokens": prof.get("max_tokens", 16000)}
        if prof.get("reasoning"):
            body["reasoning"] = prof["reasoning"]
    else:
        endpoint = "/chat/completions"
        body = {"model": model, "max_tokens": prof.get("max_tokens", 16000), "temperature": prof.get("temperature", 0.7),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if p.get("usage_include"):
            body["usage"] = {"include": True}
        if "top_p" in prof:
            body["top_p"] = prof["top_p"]
        if prof.get("reasoning"):
            body["reasoning"] = prof["reasoning"]
        if json_mode:
            body["response_format"] = {"type": "json_object"}
    body.update(prof.get("extra", {}))
    last = None
    for attempt in range(1, CFG["retries"] + 1):
        guard_stop()
        t0 = time.time()
        try:
            req = urllib.request.Request(url + endpoint, data=json.dumps(body).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=prof.get("timeout_sec", CFG["timeout_sec"])) as r:
                data = json.loads(r.read())
            if api == "messages":
                text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
                u = data.get("usage", {}) or {}
                tin, tout = u.get("input_tokens"), u.get("output_tokens")
            elif api == "responses":
                text = "".join(c.get("text", "") for it in data.get("output", []) if it.get("type") == "message"
                               for c in it.get("content", []) if c.get("type") == "output_text").strip()
                u = data.get("usage", {}) or {}
                tin, tout = u.get("input_tokens"), u.get("output_tokens")
            else:
                text = (data["choices"][0]["message"].get("content") or "").strip()
                u = data.get("usage", {}) or {}
                tin, tout = u.get("prompt_tokens"), u.get("completion_tokens")
            log(ev="call", task=task, provider=prof.get("provider"), model=model, sec=round(time.time() - t0, 1),
                attempt=attempt, tok_in=tin, tok_out=tout, cost=u.get("cost"), chars=len(text))
            if not text:
                raise ApiError("空の応答（推論で使い切った可能性）")
            return text
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            log(ev="http_error", task=task, model=model, code=e.code, detail=detail[:200])
            if e.code == 400 and ("response_format" in detail or "reasoning" in detail):
                body.pop("response_format", None)
                body.pop("reasoning", None)
                last = e
                continue
            if e.code in RETRY_HTTP:
                last = e
                time.sleep(5 * attempt)
                continue
            raise ApiError(f"HTTP {e.code}: {detail[:150]}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, ApiError) as e:
            log(ev="net_error", task=task, model=model, err=str(e)[:150])
            last = e
            time.sleep(5 * attempt)
    raise ApiError(f"{model} {task}: {last}")


def parse_json(text):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise ValueError("JSONがない")
    return json.loads(t[i:j + 1])


# ---------------------------------------------------------------- 機械検査
def corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS, k = set(), CFG["overlap_chars"]
        for d in CFG["corpus_dirs"]:
            base = (ROOT / d).resolve()
            files = [base] if base.is_file() else sorted(list(base.rglob("*.md")) + list(base.rglob("*.txt"))) if base.exists() else []
            for f in files:
                t = norm(rd(f))
                for i in range(0, max(0, len(t) - k + 1)):
                    _CORPUS.add(hash(t[i:i + k]))
    return _CORPUS


def overlap(text):
    k, c, t = CFG["overlap_chars"], corpus(), norm(text)
    for i in range(0, max(0, len(t) - k + 1)):
        if hash(t[i:i + k]) in c:
            return t[i:i + k]
    return None


def body_chars(text):
    return len(norm("\n".join(text.strip().split("\n")[1:])))


def _cp932(ch):
    try:
        ch.encode("cp932")
        return True
    except UnicodeEncodeError:
        return False


def repeated(text, prior="", n=20):
    """同じ20字が離れた位置に2回出る（場面や台詞の繰り返し）を探す。prior があればその中にも探す。"""
    t = re.sub(r"\s|＊", "", text)
    p = re.sub(r"\s|＊", "", prior)
    seen = {}
    for i in range(len(t) - n + 1):
        g = t[i:i + n]
        if g in p:
            return g
        if g in seen and i - seen[g] >= n:
            return g
        seen.setdefault(g, i)
    return None


def mech(text, n):
    iss = []
    first = text.strip().split("\n", 1)[0]
    if not re.match(rf"^# 第{n}章[　 ]\S", first):
        iss.append(f"1行目が `# 第{n}章　章題` の形ではない")
    c = body_chars(text)
    if c < CH["min"] or c > CH["max"]:
        iss.append(f"字数 {c} が範囲 {CH['min']}〜{CH['max']} の外" + (f"（あと約{CH['target'] - c}字足す。要約で済ませず、場面を会話・手順・感覚の描写で膨らませる）" if c < CH["min"] else "（削る）"))
    if "```" in text:
        iss.append("コードブロックが混入")
    if norm(text)[-1:] not in "。」』！？…）”":
        iss.append("末尾が文で完結していない")
    for pat, why in BANNED:
        m = pat.search(text)
        if m:
            iss.append(f"越えてはならない線（{why}）: 「{m.group(0)}」")
    for w in CFG["mgmt_words"]:
        if w in text:
            iss.append(f"管理用語「{w}」が本文に出ている")
    odd = sorted({ch for ch in text if "\u4e00" <= ch <= "\u9fff" and not _cp932(ch)})
    if odd:
        iss.append("字体疑い（簡体字・繁体字の混入の疑い）: " + "".join(odd[:20]))
    rp = repeated(text)
    if rp:
        iss.append(f"同じ文が繰り返されている（場面や台詞の重複。各場面は一度だけ書く）: 「{rp}」")
    ov = overlap(text)
    if ov:
        iss.append(f"既存の文章と{CFG['overlap_chars']}字以上一致: 「{ov}」")
    return iss


def clean_draft(text, n):
    t = re.sub(r"^```[a-z]*\n|\n```\s*$", "", text.strip())
    m = re.search(rf"^# 第{n}章", t, flags=re.M)
    if m and m.start() > 0:
        t = t[m.start():]
    t = re.sub(rf"^# 第{n}章[ ]", f"# 第{n}章　", t)
    return t.strip() + "\n"


def verified(quote, text):
    q = norm(quote or "")
    return len(q) >= 6 and q in norm(text)


# ---------------------------------------------------------------- CANON
def canon_issues(text):
    iss = []
    for h in CFG["canon_headings"]:
        num = re.escape(h.split(".")[0])
        if not re.search(rf"^##\s*{num}\.", text, flags=re.M):
            iss.append(f"見出し「## {h}」がない")
    if len(text) > 14000:
        iss.append("14,000字を超えている（8,000字以内を目指す）")
    for line in text.split("\n"):
        if re.search(r"ない|禁止|存在し|いな|ありえ|しな", line):
            continue
        for pat, why in BANNED:
            m = pat.search(line)
            if m:
                iss.append(f"越えてはならない線（{why}）: 「{m.group(0)}」")
    return iss


def cmd_canon(a):
    brief, tmpl = rd(ROOT / "BRIEF.md"), rd(ROOT / "prompts" / "design.md")
    system = "あなたは日本語の小説の設計者です。依頼文の指示と出力形式に厳密に従い、指定された成果物だけを返します。"
    p1, p2 = ROOT / "work" / "canon_p1.md", ROOT / "work" / "canon_p2.md"
    base = sec("BRIEF", brief) + "\n" + tmpl
    fixf = ROOT / "notes" / "CANON_FIX.md"
    if fixf.exists() and (ROOT / "work" / "old" / "CANON.draft.prev.md").exists():
        base += "\n\n# 前回案（v1）\n" + rd(ROOT / "work" / "old" / "CANON.draft.prev.md") + "\n\n" + rd(fixf)
    if not p1.exists():
        t = chat(CFG["workers"]["designer"], system, base + "\n\n# 今回の担当\n**## 1. 舞台 〜 ## 4. 不変条件 だけ**を書く（合計4,000字以内）。5〜8は次の呼び出しで書く。", "design1").strip()
        wr(p1, re.sub(r"^```[a-z]*\n|\n```\s*$", "", t))
        print("CANON 前半（1〜4）を作成。続きを同じコマンドで")
        if time.time() - T0 > 60:
            return
    if not p2.exists():
        t = chat(CFG["workers"]["designer"], system, base + "\n\n# すでに決まった前半（矛盾させない）\n" + rd(p1)
                 + "\n\n# 今回の担当\n**## 5. 糸の中身 〜 ## 8. 差し込み申告 だけ**を書く（合計4,500字以内。見出しは `## 5.` のように）。前半は繰り返さない。", "design2").strip()
        wr(p2, re.sub(r"^```[a-z]*\n|\n```\s*$", "", t))
    text = rd(p1).strip() + "\n\n" + rd(p2).strip()
    iss = canon_issues(text)
    if iss:
        stamp = time.strftime("%H%M%S")
        for p in (p1, p2):
            p.rename(ROOT / "work" / "old" / f"{p.stem}.{stamp}.md")
        print("CANON 不備（前後半とも退避。もう一度実行すると作り直す）:", iss, file=sys.stderr)
        sys.exit(3)
    wr(ROOT / "canon" / "CANON.draft.md", text + "\n")
    sha = hashlib.sha256((text + "\n").encode("utf-8")).hexdigest()
    print(f"CANON案 OK（{len(text)}字）。sha256先頭8字={sha[:8]}。人が読んで承認したら approve-canon --sha {sha[:8]}")


def cmd_approve(a):
    d = ROOT / "canon" / "CANON.draft.md"
    sha = hashlib.sha256(d.read_bytes()).hexdigest()
    if len(a.sha) < 8 or not sha.startswith(a.sha):
        sys.exit("sha が一致しない（人が承認した版の指紋を入力する）")
    c = ROOT / "canon" / "CANON.md"
    if c.exists():
        os.chmod(c, 0o644)
    c.write_bytes(d.read_bytes())
    wr(ROOT / "canon" / "CANON.sha256", sha + "\n")
    os.chmod(c, 0o444)
    print("CANON を確定・固定した:", sha[:12])


def canon_text():
    c = ROOT / "canon" / "CANON.md"
    if not c.exists():
        sys.exit("CANON が未確定（canon → approve-canon）")
    if hashlib.sha256(c.read_bytes()).hexdigest() != rd(ROOT / "canon" / "CANON.sha256").strip():
        print("ESCALATE CANON_MODIFIED", file=sys.stderr)
        sys.exit(3)
    t = c.read_text(encoding="utf-8")
    am = rd(ROOT / "canon" / "AMENDMENTS.md")
    if am and am.strip():
        t += "\n\n# CANON 改正（人が承認した変更。上の本文より優先する）\n" + am.strip() + "\n"
    return t


# ---------------------------------------------------------------- 章
def progress():
    p = RUN / "state" / "progress.json"
    return json.loads(rd(p)) if p.exists() else {"chapters": {}, "escalated": None}


def save_progress(pg):
    wr(RUN / "state" / "progress.json", json.dumps(pg, ensure_ascii=False, indent=1))


def make_packet(n, canon, feedback=""):
    brief = rd(ROOT / "BRIEF.md")
    rules = between(brief, "<!-- RULES:BEGIN -->", "<!-- RULES:END -->")
    role = between(brief, f"<!-- ROLE:{nn(n)} -->", f"<!-- /ROLE:{nn(n)} -->")
    prev = rd(RUN / "chapters" / f"ch{nn(n - 1)}.md") if n > 1 else ""
    s = sec("共通執筆ルール（BRIEF）", rules) + sec("CANON", canon) + sec(f"この章の機能（BRIEF 第{n}章）", role)
    s += sec("LEDGER（これまでの章の記録）", rd(RUN / "state" / "LEDGER.md") or "（まだない。第1章）")
    if prev:
        s += sec("前章の結び", prev[-CFG["prev_tail_chars"]:])
    plot = rd(RUN / "plots" / f"ch{nn(n)}" / "final.md")
    if plot:
        s += sec("確定プロット（必ずこれに従って肉付けする）", plot + "\n\n【扱い】場面の順序・行為の連鎖・台詞の種・予想を外す一手・置く細部は変えない。足してよいのは、会話の肉付けと、音・におい・手触り・温度の描写だけ。細部の意味を地の文で説明しない。各場面は約" + str(CH["target"] // 3) + "字の厚みで書く。")
    w = rd(ROOT / "prompts" / "write.md")
    for k, v in {"{{N}}": str(n), "{{TARGET}}": str(CH["target"]), "{{MINC}}": str(CH["min"]), "{{MAXC}}": str(CH["max"])}.items():
        w = w.replace(k, v)
    s += "\n" + w
    if feedback:
        s += "\n\n# 前の稿への指摘（必ず直す。直しても CANON と台帳に矛盾させない）\n" + feedback
    return s, rules, role


def fan_out(writers, packet, n, wdir, a):
    def one(w):
        f = wdir / f"a{a}_{w['name']}.md"
        if f.exists():
            return w["name"], rd(f), None
        try:
            t = clean_draft(chat(w, CFG["writer_system"], packet + ("\n\n" + w["angle"] if w.get("angle") else ""), f"write:{w['name']}"), n)
            wr(f, t)
            return w["name"], t, None
        except Exception as e:  # 1人の失敗は全体の失敗ではない
            return w["name"], None, str(e)
    with cf.ThreadPoolExecutor(max_workers=len(writers)) as ex:
        return list(ex.map(one, writers))


def scenes_of(plot):
    body = plot.split("# 照合表")[0]
    sc = re.split(r"^## 場面\d+[：:].*$", body, flags=re.M)
    heads = re.findall(r"^## 場面\d+[：:].*$", body, flags=re.M)
    out = []
    for h, b in zip(heads, sc[1:]):
        out.append((h, b.split("\n## 結び")[0].strip()))
    return out


def plot_write(n, canon, wdir, a, fb):
    """場面ごとに書かせて連結する。短く縮む書き手の分量を、場面単位で制御する。"""
    plot = rd(RUN / "plots" / f"ch{nn(n)}" / "final.md")
    sc = scenes_of(plot)
    if not sc:
        return [("qw", None, "プロットから場面が取れない")]
    ctx = plot_context(n, canon)
    m3 = re.search(r"^## 語りの手触り.*?(?=^# 照合表|\Z)", plot, flags=re.M | re.S)
    m4 = re.search(r"^# 照合表.*", plot, flags=re.M | re.S)
    ctx += sec("語りの手触り（全場面共通）", m3.group(0).strip() if m3 else "") + sec("照合表（守る値）", m4.group(0).strip() if m4 else "")
    per = CH["target"] // len(sc)
    smin, smax = int(per * 0.9), int(per * 1.4)
    brief = rd(ROOT / "BRIEF.md")
    m = re.search(rf"\*\*第{n}章[　 ](.+?)\*\*", brief)
    title = m.group(1).strip() if m else "（題）"
    parts = []
    for k, (h, b) in enumerate(sc, 1):
        f = wdir / f"a{a}_scene{k}.md"
        if not f.exists():
            budget(f"場面{k}", CFG["plot"].get("time_budget_sec", 55))
            prompt = ctx
            prompt += sec("直前の本文の末尾（ここから続く。繰り返さない）", parts[-1][-700:]) if parts else ""
            prompt += sec(f"いま書く場面：{h.lstrip('# ').strip()}（これだけを書く。前の場面は書かない）", b)
            last = ""
            if k == len(sc):
                m2 = re.search(r"^## 結び.*?(?=^## 語りの手触り|\Z)", plot.split("# 照合表")[0], flags=re.M | re.S)
                last = "\n最後の場面なので、次の「結び」の気配で終える（説明で締めない）：\n" + (m2.group(0).strip() if m2 else "") + "\n"
            p = (rd(ROOT / "prompts" / "write_scene.md").replace("{{N}}", str(n)).replace("{{K}}", str(k)).replace("{{KK}}", str(len(sc)))
                 .replace("{{SC}}", str(per)).replace("{{SMIN}}", str(smin)).replace("{{SMAX}}", str(smax)).replace("{{LASTNOTE}}", last))
            if fb and a > 1:
                p += "\n# 前の稿への指摘（直す）\n" + fb
            best, txt = None, ""
            for tr in range(3):
                try:
                    txt = chat(CFG["plot_writer"], CFG["writer_system"], prompt + (f"\n\n（前回は{body_chars(txt)}字{'で短すぎ' if body_chars(txt) < smin else ''}{'で、繰り返しがありました' if repeated(txt, ''.join(parts)) else ''}。{smin}〜{smax}字に収める。{'手順・会話・感覚を足す' if body_chars(txt) < smin else 'この場面より先の出来事・前の場面や自分の文の繰り返しは書かない'}）" if tr and txt else ""), f"scene:{k}")
                except Exception as e:
                    if best is None:
                        return [("qw", None, str(e)[:120])]
                    break
                txt = re.sub(r"^```[a-z]*\n|\n```\s*$", "", txt.strip())
                txt = re.sub(r"^#+ .*\n", "", txt).strip()
                c = body_chars(txt)
                rep = repeated(txt, "".join(parts))
                bad = (1 if rep else 0, 0 if smin <= c <= int(smax * 1.15) else 1, abs(c - per))
                if best is None or bad < best[0]:
                    best = (bad, txt)
                if bad[0] == 0 and bad[1] == 0:
                    break
            txt = best[1]
            wr(f, txt)
        parts.append(rd(f).strip())
    text = f"# 第{n}章　{title}\n\n" + "\n\n＊\n\n".join(parts) + "\n"
    wr(wdir / f"a{a}_qw.md", text)
    return [("qw", text, None)]


def edit(n, valid, rules, role, canon, wdir, a):
    """匿名にして比べ、採用稿を選ばせる。引用が本文に無ければ採らない。"""
    names = [k for k, _ in valid]
    order = names[:]
    random.Random(f"{n}-{a}").shuffle(order)
    labels = {chr(65 + i): nm for i, nm in enumerate(order)}
    texts = {chr(65 + i): dict(valid)[nm] for i, nm in enumerate(order)}
    body = sec("BRIEF 共通ルール", rules) + sec("CANON", canon) + sec(f"この章の機能（第{n}章）", role)
    for lb, t in texts.items():
        body += sec(f"稿{lb}", t)
    prompt = body + "\n" + rd(ROOT / "prompts" / "edit.md").replace("{{LABELS}}", "・".join(texts))
    note = ""
    for k in range(2):
        out = chat(CFG["workers"]["editor"], "あなたは厳格で公平な小説編集者です。JSONだけを返します。", prompt + note, "edit", json_mode=True)
        try:
            j = parse_json(out)
            pick = j["pick"]
            assert pick in texts
        except Exception as e:
            note = f"\n\n（前回の出力は形式不正: {e}。JSONだけを返す）"
            continue
        ev = [x for x in j.get("evidence", []) if x.get("draft") == pick]
        ok = [x for x in ev if verified(x.get("quote"), texts[pick])]
        rec = {"labels": labels, "pick": pick, "picked_writer": labels[pick], "reason": j.get("reason"),
               "scores": j.get("scores"), "evidence_ok": len(ok), "evidence_total": len(ev), "risk": j.get("risk")}
        wr(wdir / f"a{a}_edit.json", json.dumps(rec, ensure_ascii=False, indent=1))
        if len(ok) >= 2:
            return labels[pick], rec
        note = f"\n\n（前回の引用は本文に一字一句ありませんでした: 照合に通ったのは{len(ok)}件。採用稿からそのまま写して出し直す）"
    # 照合に通らない：スコア合計で決めるが、記録に残す
    sc = (j.get("scores") if 'j' in dir() else None) or {}
    best = max(texts, key=lambda lb: sum((sc.get(lb) or {}).values()) if isinstance(sc.get(lb), dict) else 0)
    rec = {"labels": labels, "pick": best, "picked_writer": labels[best], "fallback": "editor_unverified"}
    wr(wdir / f"a{a}_edit.json", json.dumps(rec, ensure_ascii=False, indent=1))
    return labels[best], rec


def check(n, text, rules, role, canon, wdir, a):
    ledger = rd(RUN / "state" / "LEDGER.md")
    prompt = (sec("BRIEF 共通ルール", rules) + sec(f"この章の機能（第{n}章）", role) + sec("CANON", canon)
              + sec("LEDGER", ledger or "（まだない）") + sec(f"原稿（第{n}章）", text)
              + "\n" + rd(ROOT / "prompts" / "check.md").replace("{{N}}", str(n)))
    src = {"CANON": canon, "LEDGER": ledger, "BRIEF": rules + role}
    out = chat(CFG["workers"]["checker"], "あなたは厳格な整合の検査役です。JSONだけを返します。", prompt, "check", json_mode=True)
    try:
        issues = parse_json(out).get("issues", [])
    except Exception:
        issues = []
        log(ev="check_unparsable", n=n)
    ok, bad = [], []
    for it in issues:
        qd, k = it.get("quote_draft"), it.get("kind")
        good = verified(qd, text) and not re.search(r"一致している|矛盾しない|問題(ない|なし)|検査不能|整合している", it.get("explain", ""))
        if good and k != "validity" and it.get("source") in src:
            good = verified(it.get("quote_source"), src[it["source"]])
        (ok if good else bad).append(it)
    wr(wdir / f"a{a}_check.json", json.dumps({"verified": ok, "unverified": bad}, ensure_ascii=False, indent=1))
    return ok


def ledger_section(n, text, canon):
    prompt = (sec("CANON", canon) + sec(f"確定した第{n}章", text) + "\n"
              + rd(ROOT / "prompts" / "ledger.md").replace("{{N}}", str(n)).replace("{{NN}}", nn(n)))
    fields = ["SUMMARY:", "FACT:", "STATE:", "THREAD:", "INSERT:", "OPEN:", "LAST:"]
    for k in range(2):
        out = chat(CFG["workers"]["ledger"], "あなたは正確な記録係です。指定の形式の本文だけを返します。", prompt, "ledger").strip()
        out = re.sub(r"^```[a-z]*\n|\n```\s*$", "", out)
        keep, dropped = [], []
        for line in out.split("\n"):
            if line.startswith("FACT:"):
                m = re.search(r"[｜|]\s*「(.+?)」", line)
                (keep if m and verified(m.group(1), text) else dropped).append(line)
            else:
                keep.append(line)
        miss = [f for f in fields if not any(l.startswith(f) for l in keep)]
        facts = [l for l in keep if l.startswith("FACT:")]
        if not miss and len(facts) >= 3:
            if dropped:
                log(ev="ledger_facts_dropped", n=n, dropped=dropped)
            return "\n".join(keep).strip() + "\n"
        log(ev="ledger_retry", n=n, miss=miss, facts=len(facts))
    return None


def budget(label, limit=None):
    """この呼び出しの時間の予算を超えそうなら、ここまでの結果を残して止まる（同じコマンドを再度打てば続きから）。"""
    if not os.environ.get("TEAM_NO_BUDGET") and time.time() - T0 > (limit or CFG.get("time_budget_sec", 100)):
        print(f"CONTINUE（{label}の前で一旦停止。同じコマンドをもう一度実行する）")
        sys.exit(0)


def cmd_write(a):
    global RUN
    n, mode = int(a.n), a.mode
    RUN = ROOT / "runs" / mode
    guard_stop()
    canon = canon_text()
    pg = progress()
    if pg["chapters"].get(str(n), {}).get("status") == "accepted":
        print(f"第{n}章は確定済み")
        return
    if n > 1 and pg["chapters"].get(str(n - 1), {}).get("status") != "accepted":
        sys.exit(f"第{n - 1}章が未確定")
    writers = [CFG["aion"]] if mode == "aion" else [CFG["plot_writer"]] if mode == "plot" else CFG["writers"]
    wdir = RUN / "work" / f"ch{nn(n)}"
    sf = wdir / "state.json"
    st = json.loads(rd(sf)) if sf.exists() else {"att": 1, "fb": ""}
    picked, valid = None, []
    for att in range(st["att"], CFG["max_attempts"] + 1):
        fb = st["fb"]
        packet, rules, role = make_packet(n, canon, fb)
        wr(wdir / f"a{att}_packet.md", packet)
        if mode == "plot":
            res = plot_write(n, canon, wdir, att, fb)
        else:
            if not all((wdir / f"a{att}_{w['name']}.md").exists() for w in writers):
                budget("執筆")
            res = fan_out(writers, packet, n, wdir, att)
        valid, mech_fb = [], []
        for name, t, err in res:
            if err:
                mech_fb.append(f"[{name}] 呼び出し失敗: {err[:120]}")
                continue
            iss = mech(t, n)
            wr(wdir / f"a{att}_{name}.mech.json", json.dumps(iss, ensure_ascii=False))
            (mech_fb.append(f"[{name}] " + " / ".join(iss)) if iss else valid.append((name, t)))
        log(ev="attempt", n=n, mode=mode, att=att, valid=[v[0] for v in valid], failed=len(res) - len(valid))
        if not valid:
            st = {"att": att + 1, "fb": "機械検査で全稿が不合格:\n" + "\n".join(mech_fb)}
            wr(sf, json.dumps(st, ensure_ascii=False))
            continue
        ef = wdir / f"a{att}_edit.json"
        cached = json.loads(rd(ef)) if ef.exists() else None
        if mode == "team" and len(valid) > 1:
            if cached and cached.get("picked_writer") in dict(valid):
                who, rec = cached["picked_writer"], cached
            else:
                budget("編集")
                who, rec = edit(n, valid, rules, role, canon, wdir, att)
        else:
            who, rec = valid[0][0], {"picked_writer": valid[0][0], "single": True}
        text = dict(valid)[who]
        cf_ = wdir / f"a{att}_check.json"
        if cf_.exists():
            issues = json.loads(rd(cf_))["verified"]
        else:
            budget("検査")
            issues = check(n, text, rules, role, canon, wdir, att)
        high = [i for i in issues if i.get("severity") == "high"]
        if high and att < CFG["max_attempts"]:
            st = {"att": att + 1, "fb": "整合の検査役の指摘（引用つき・照合済み）:\n" + "\n".join(
                f"- 〔{i.get('kind')}〕「{i.get('quote_draft')}」 {i.get('explain')}" for i in high)}
            wr(sf, json.dumps(st, ensure_ascii=False))
            continue
        if high:
            pg["escalated"] = {"chapter": n, "why": "高重大度の整合指摘が残った", "issues": high}
            save_progress(pg)
            print("ESCALATE CHAPTER_EXHAUSTED（人の判断が要る）: work/ を確認", file=sys.stderr)
            sys.exit(3)
        picked = (who, rec, att, issues)
        break
    if not picked:
        pg["escalated"] = {"chapter": n, "why": "全稿が機械検査に通らなかった", "last": st["fb"][:500]}
        save_progress(pg)
        print("ESCALATE CHAPTER_EXHAUSTED", file=sys.stderr)
        sys.exit(3)
    who, rec, att, issues = picked
    text = dict(valid)[who]
    lf = wdir / "ledger_section.md"
    if lf.exists():
        sect = rd(lf)
    else:
        budget("台帳")
        sect = ledger_section(n, text, canon)
        if sect:
            wr(lf, sect)
    if sect is None:
        pg["escalated"] = {"chapter": n, "why": "台帳が検証つきで作れなかった"}
        save_progress(pg)
        print("ESCALATE LEDGER_FAILED", file=sys.stderr)
        sys.exit(3)
    wr(RUN / "chapters" / f"ch{nn(n)}.md", text)
    led = RUN / "state" / "LEDGER.md"
    wr(led, (rd(led) + "\n" if rd(led) else "") + sect)
    pg["chapters"][str(n)] = {"status": "accepted", "attempts": att, "writer": who, "chars": body_chars(text),
                              "low_issues": len(issues)}
    pg["escalated"] = None
    save_progress(pg)
    log(ev="accepted", n=n, mode=mode, writer=who, att=att)
    print(f"第{n}章 確定（{mode}）: 採用={who}, 字数={body_chars(text)}, 稿={att}, 低重大度の指摘={len(issues)}")


# ---------------------------------------------------------------- プロットの反復（グループ1）
def plot_context(n, canon):
    brief = rd(ROOT / "BRIEF.md")
    rules = between(brief, "<!-- RULES:BEGIN -->", "<!-- RULES:END -->")
    role = between(brief, f"<!-- ROLE:{nn(n)} -->", f"<!-- /ROLE:{nn(n)} -->")
    prev = rd(RUN / "chapters" / f"ch{nn(n - 1)}.md") if n > 1 else ""
    s = sec("共通執筆ルール（BRIEF）", rules) + sec("CANON", canon) + sec(f"この章の機能（BRIEF 第{n}章）", role)
    s += sec("LEDGER（これまでの章の記録）", rd(RUN / "state" / "LEDGER.md") or "（まだない。第1章）")
    if prev:
        s += sec("前章の結び", prev[-CFG["prev_tail_chars"]:])
    return s


def plot_stage(jobs, label):
    """jobs: [(path, profile, system, prompt)]。既にあるファイルは再利用。足りないぶんだけ並列に呼ぶ。"""
    todo = [j for j in jobs if not j[0].exists()]
    if todo:
        budget(label, CFG["plot"].get("time_budget_sec", 55))

        def one(j):
            f, prof, system, prompt = j
            try:
                wr(f, chat(prof, system, prompt, f"plot:{label}:{prof['name']}"))
                return None
            except Exception as e:
                return f"{prof['name']}: {str(e)[:120]}"
        with cf.ThreadPoolExecutor(max_workers=len(todo)) as ex:
            errs = [e for e in ex.map(one, todo) if e]
        if errs:
            log(ev="plot_stage_errors", label=label, errs=errs)
    return [j[0] for j in jobs if j[0].exists()]


def plan_of(raw):
    m = re.search(r"^#\s*統合案\s*$(.*)", raw, flags=re.M | re.S)
    return (m.group(1) if m else raw).strip()


def cmd_plot(a):
    global RUN
    n, RUN = int(a.n), ROOT / "runs" / "plot"
    guard_stop()
    canon = canon_text()
    P = CFG["plot"]
    pd = RUN / "plots" / f"ch{nn(n)}"
    if (pd / "final.md").exists():
        print(f"第{n}章のプロットは確定済み: {pd / 'final.md'}")
        return
    ctx = plot_context(n, canon)
    sub = lambda t: t.replace("{{N}}", str(n))
    SYS = "あなたは経験豊かな小説の構成作家です。"
    models = P["models"]
    seed_p = sub(rd(ROOT / "prompts" / "plot_seed.md"))
    files = plot_stage([(pd / f"seed_{m['name']}.md", dict(m, temperature=1.0), SYS, ctx + "\n" + seed_p) for m in models], "シード")
    if len(files) < 2:
        sys.exit("シード案が2つ以上できなかった（logs を確認）")
    plans = {f.stem.split("_", 1)[1]: rd(f) for f in files}
    for r in range(1, P["rounds"] + 1):
        ref_p = sub(rd(ROOT / "prompts" / "plot_refine.md"))
        jobs = []
        for m in models:
            names = list(plans)
            random.Random(f"{n}-{r}-{m['name']}").shuffle(names)
            body = "".join(sec(f"案 P{i + 1}", plans[nm]) for i, nm in enumerate(names))
            jobs.append((pd / f"r{r}_{m['name']}.md", dict(m, temperature=0.9), SYS, ctx + "\n" + body + "\n" + ref_p))
        fs = plot_stage(jobs, f"統合{r}")
        if not fs:
            sys.exit(f"統合{r}回目が全員失敗（logs を確認）")
        plans = {f.stem.split("_", 1)[1]: plan_of(rd(f)) for f in fs}
    body = "".join(sec(f"案 P{i + 1}", t) for i, (_, t) in enumerate(sorted(plans.items())))
    fin_p = sub(rd(ROOT / "prompts" / "plot_final.md"))
    for k in range(2):
        out = pd / f"final_try{k + 1}.md"
        got = plot_stage([(out, P["synth"], "あなたは作品の主筆です。", ctx + "\n" + body + "\n" + fin_p)], "最終")
        t = rd(out) if got else ""
        main_part = t.split("# 照合表")[0]
        bad = [w for w in CFG["mgmt_words"] if w in main_part]
        if t and "# 最終プロット" in t and 1200 <= len(t) <= 6000 and not bad:
            wr(pd / "final.md", t.strip() + "\n")
            log(ev="plot_done", n=n, chars=len(t))
            print(f"第{n}章のプロット確定（{len(models)}モデル × シード+{P['rounds']}周 → 主筆の統合）: {pd / 'final.md'}")
            return
        if t:
            log(ev="plot_final_bad", n=n, bad=bad, chars=len(t))
            try:
                out.rename(pd / f"final_bad{k + 1}.md")
            except OSError:
                pass
    sys.exit("最終プロットが基準（見出し・字数・管理用語なし）を満たさない: logs と plots/ を確認")


# ---------------------------------------------------------------- 比べる
def inserts_of(mode, n):
    t = rd(ROOT / "runs" / mode / "state" / "LEDGER.md")
    m = re.search(rf"^## CH{nn(n)}\b(.*?)(?=^## CH|\Z)", t, flags=re.M | re.S)
    return "\n".join(l for l in (m.group(1) if m else "").split("\n") if l.startswith("INSERT:")) or "INSERT: （記録なし）"


def cmd_judge(a):
    n = int(a.n)
    ma = a.a
    texts = {m: final_text(m, n, a.raw) for m in (ma, "aion")}
    if not all(texts.values()):
        sys.exit(f"{ma} と aion の両方で第N章が確定している必要がある")
    canon = canon_text()
    brief = rd(ROOT / "BRIEF.md")
    rules = between(brief, "<!-- RULES:BEGIN -->", "<!-- RULES:END -->")
    role = between(brief, f"<!-- ROLE:{nn(n)} -->", f"<!-- /ROLE:{nn(n)} -->")
    order = [ma, "aion"]
    random.Random(f"judge-{n}-{ma}").shuffle(order)
    lab = {"A": order[0], "B": order[1]}
    body = sec("BRIEF 共通ルール", rules) + sec("CANON", canon) + sec(f"この章の機能（第{n}章）", role)
    for lb, m in lab.items():
        body += sec(f"稿{lb}", texts[m]) + sec(f"稿{lb} の差し込みの記録", inserts_of(m, n))
    body += """
あなたは匿名の2稿を比べる審査員です。次の6軸を各1〜5点で採点し、総合でどちらを採るか選んでください。
- rule：機能・糸・禁止・CANON整合の遵守　- yohaku：決められていない所での意外で良い差し込み
- atofuki：差し込みの後始末（記録に載せ、本文の中で筋が通っているか）　- chara：人物が生きているか
- bun：文章（説明過多でなく、余白と緩急があるか）　- pace：章の密度配分が機能どおりか
出力はJSONのみ：{"scores":{"A":{"rule":0,"yohaku":0,"atofuki":0,"chara":0,"bun":0,"pace":0},"B":{...}},"pick":"A|B","reason":"150字以内","evidence":[{"draft":"A|B","quote":"その稿からそのまま写した30字以内","why":"何の根拠か"}, ...4件以上]}
引用は一字一句そのまま。照合に通らない引用は捨てられる。"""
    j, note = None, ""
    for k in range(3):
        out = chat(CFG["workers"]["judge"], "あなたは公平な審査員です。JSONだけを返します。", body + note, "judge", json_mode=True)
        try:
            j = parse_json(out)
            assert j.get("pick") in lab and isinstance(j.get("scores"), dict) and all(x in j["scores"] for x in lab)
            break
        except Exception as e:
            wr(ROOT / "notes" / f"judge_bad_{k}.txt", out)
            j, note = None, f"\n\n（前回の出力は形式不正でした。pick は \"A\" か \"B\" のどちらか一方、scores は A と B の両方を含めて、JSONだけを返す）"
    if j is None:
        sys.exit("審査役が正しい形式で返さなかった（notes/judge_bad_*.txt を確認）")
    ev = j.get("evidence", [])
    for x in ev:
        x["verified"] = verified(x.get("quote"), texts[lab[x.get("draft", "A")]]) if x.get("draft") in lab else False
    j["labels"] = lab
    j["evidence_verified"] = sum(1 for x in ev if x["verified"])
    wr(ROOT / "notes" / f"EVAL_ch{nn(n)}_{ma}.json", json.dumps(j, ensure_ascii=False, indent=1))
    winner = lab.get(j.get("pick"))
    with open(ROOT / "notes" / "EVAL.md", "a", encoding="utf-8") as f:
        f.write(f"\n## 第{n}章 {time.strftime('%Y-%m-%d %H:%M')}（{ma} vs aion、{'raw' if a.raw else '校正後があれば校正後'}）\n- 勝ち: **{winner}**（A={lab['A']}, B={lab['B']}）／引用の照合 {j['evidence_verified']}/{len(ev)}\n"
                f"- スコア: {json.dumps({lab[k]: v for k, v in j.get('scores', {}).items()}, ensure_ascii=False)}\n- 理由: {j.get('reason')}\n")
    print(f"第{n}章 審査: 勝ち={winner} 引用照合={j['evidence_verified']}/{len(ev)} scores={ {lab[k]: v for k, v in j.get('scores', {}).items()} }")


# ---------------------------------------------------------------- 校正（Mac側の codex / ChatGPT / agy に渡す）
PROOF_PROMPT = """あなたは日本語の校正者です。下の「原稿」を厳密に校正し、**修正の一覧だけ**をJSONで返してください。原稿全体を書き直してはいけません。

# 見ること
- 簡体字・繁体字・日本で使わない字形の混入（例：这、個の旧字体ではなく中国語の字形、說/説の混在など）。日本の常用漢字・人名用漢字に直す。
- 誤字脱字、送りがな、表記ゆれ（同じ語の漢字/かな混在、数字の書き方）、助詞の誤り、主語・人称・呼び名の揺れ、読点・括弧の不整合、中国語的な言い回し。
- 内容・文体・語り・固有名詞・数値は変えない。意味が変わる直しは出さない。
- 舟の語（艫・舳先・舫い・櫓・櫂）や「三度半」は固有の表現で、誤りではない。直さない。「字体」とは、簡体字・繁体字など日本で使わない字形が実際に原稿にある場合だけ。\n- **確信のない直しは出さない。** 正しい語（例：舫い綱、櫓、艫など舟の語）を誤字と決めつけて別の語に変えない。迷ったら出さない。

# 厳守
- ファイルの読み書き・コマンド実行・ツール使用は一切しない。答えは標準出力にJSONだけを返す。前置き・説明・表・コードフェンスは付けない。

# 出力（JSONのみ）
{"corrections":[{"quote":"原稿からそのまま写した、原稿中に1か所だけ現れる20〜60字","replace":"直した後の同じ範囲","kind":"字体|誤字|表記|助詞|人称|文法|その他","reason":"30字以内"}]}
- quote は一字一句そのまま。原稿に無い、または複数か所に現れる quote は機械が捨てる。
- 直す所がなければ {"corrections":[]}。"""


def src_text(n):
    """校正の入力：Opus の直しを適用した稿（polished1）があればそれ、なければ確定稿。"""
    return rd(RUN / "polished1" / f"ch{nn(n)}.md") or rd(RUN / "chapters" / f"ch{nn(n)}.md")


def final_text(mode, n, raw=False):
    r = ROOT / "runs" / mode
    return (None if raw else rd(r / "polished" / f"ch{nn(n)}.md")) or rd(r / "chapters" / f"ch{nn(n)}.md")


def apply_corrections(text, cs, lo, hi, minq, guard=False):
    out, ok, bad = text, [], []
    for c in cs:
        q, r = c.get("quote", ""), c.get("replace", "")
        if guard:
            odd = [ch for ch in q if "\u4e00" <= ch <= "\u9fff" and not _cp932(ch)]
            lost = [w for w in CFG.get("protected_terms", []) if w in q and w not in r]
            if c.get("kind") == "字体" and not odd:
                bad.append({**c, "why": "字体の直しだが、quoteに字体疑いの字がない（機械が却下）"})
                continue
            if lost:
                bad.append({**c, "why": f"保護語を消す直し: {lost}"})
                continue
        if len(q) < minq or text.count(q) != 1 or not (lo <= len(r) / max(1, len(q)) <= hi) or r == q:
            bad.append({**c, "why": "quoteが原稿に一意でない／変更が大きすぎ小さすぎ／変更なし"})
            continue
        out = out.replace(q, r)
        ok.append(c)
    return out, ok, bad


def odd_report(text):
    odd = [(ch, text.index(ch)) for ch in sorted({c for c in text if "\u4e00" <= c <= "\u9fff" and not _cp932(c)})]
    return "\n".join(f"- 「{c}」 付近: {text[max(0, i - 10):i + 10]!r}" for c, i in odd) or "（機械検査では見つからず）"


def cmd_polish(a):
    global RUN
    n, RUN = int(a.n), ROOT / "runs" / a.mode
    text = rd(RUN / "chapters" / f"ch{nn(n)}.md")
    if not text:
        sys.exit("確定した章がない")
    pk = RUN / "proof" / f"ch{nn(n)}.polish.packet.md"
    wr(pk, rd(ROOT / "prompts" / "polish.md") + "\n\n# 原稿\n\n" + text)
    print(f"日本語直し・文学化のパケット: {pk}\nMac で agy（Opus）に渡し、返ったJSONだけを {RUN / 'proof' / f'ch{nn(n)}.polish.json'} に置き、polish-apply {n} --mode {a.mode} を実行する")


def cmd_polish_apply(a):
    global RUN
    n, RUN = int(a.n), ROOT / "runs" / a.mode
    text = rd(RUN / "chapters" / f"ch{nn(n)}.md")
    raw = rd(RUN / "proof" / f"ch{nn(n)}.polish.json")
    if not text or not raw:
        sys.exit("章または polish.json がない")
    cs = parse_json(raw).get("corrections", [])
    out, ok, bad = apply_corrections(text, cs, 0.5, 2.0, 10)
    wr(RUN / "polished1" / f"ch{nn(n)}.md", out)
    wr(RUN / "proof" / f"ch{nn(n)}.polish.applied.json", json.dumps({"applied": ok, "rejected": bad}, ensure_ascii=False, indent=1))
    print(f"第{n}章 日本語直し: 適用{len(ok)}件 / 却下{len(bad)}件 → {RUN / 'polished1' / f'ch{nn(n)}.md'}")


def cmd_proofread(a):
    global RUN
    n, RUN = int(a.n), ROOT / "runs" / a.mode
    text = src_text(n)
    if not text:
        sys.exit("確定した章がない")
    pk = RUN / "proof" / f"ch{nn(n)}.packet.md"
    wr(pk, PROOF_PROMPT + "\n\n# 機械検査の参考（字体疑い）\n" + odd_report(text) + "\n\n# 原稿\n\n" + text)
    if getattr(a, "auto", False):
        out = chat(CFG["proof_worker"], "あなたは日本語の校正者です。JSONだけを返します。", rd(pk), "proof")
        wr(RUN / "proof" / f"ch{nn(n)}.corrections.json", out)
        cmd_proofread_apply(a)
        return
    print(f"校正パケット: {pk}\n返ってきたJSONを {RUN / 'proof' / f'ch{nn(n)}.corrections.json'} に置き、proofread-apply {n} --mode {a.mode} を実行する")


def cmd_proofread_apply(a):
    global RUN
    n, RUN = int(a.n), ROOT / "runs" / a.mode
    text = src_text(n)
    raw = rd(RUN / "proof" / f"ch{nn(n)}.corrections.json")
    if not text or not raw:
        sys.exit("章または corrections.json がない")
    cs = parse_json(raw).get("corrections", [])
    out, ok, bad = apply_corrections(text, cs, 0.5, 2.0, 6, guard=True)
    odd = sorted({ch for ch in out if "\u4e00" <= ch <= "\u9fff" and not _cp932(ch)})
    wr(RUN / "polished" / f"ch{nn(n)}.md", out)
    wr(RUN / "proof" / f"ch{nn(n)}.applied.json", json.dumps({"applied": ok, "rejected": bad, "odd_left": odd}, ensure_ascii=False, indent=1))
    print(f"第{n}章 校正: 適用{len(ok)}件 / 却下{len(bad)}件 / 字体疑い残り={''.join(odd) or 'なし'} → {RUN / 'polished' / f'ch{nn(n)}.md'}")


# ---------------------------------------------------------------- 補助
def cmd_ping(a):
    seen = {}
    for nm, p in [(k, v) for k, v in CFG["workers"].items()] + [(w["name"], w) for w in CFG["writers"]] + [("aion", CFG["aion"])]:
        seen.setdefault((p.get("provider"), p.get("model") or p.get("model_env")), dict(p, max_tokens=600, reasoning=p.get("reasoning") and {"effort": "low"}))
    for (prov, _), p in seen.items():
        model = resolve(p)[3]
        t0 = time.time()
        try:
            o = chat(p, "簡潔に答える", "「OK」とだけ返答してください。", "ping")
            print(f"OK   [{prov}/{p.get('api', 'chat')}] {model} ({time.time() - t0:.1f}s) {o[:20]!r}")
        except Exception as e:
            print(f"FAIL [{prov}/{p.get('api', 'chat')}] {model}: {str(e)[:140]}")


def cmd_status(a):
    for mode in ("team", "aion", "plot"):
        p = ROOT / "runs" / mode / "state" / "progress.json"
        if not p.exists():
            print(f"[{mode}] 未着手")
            continue
        pg = json.loads(rd(p))
        cost = 0.0
        for l in (rd(ROOT / "runs" / mode / "logs" / "run.jsonl") or "").splitlines():
            try:
                cost += float(json.loads(l).get("cost") or 0)
            except Exception:
                pass
        print(f"[{mode}] 確定: {sorted(pg['chapters'])}  escalated={pg.get('escalated') and pg['escalated'].get('why')}  費用(USD)≈{cost:.3f}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for c in ("ping", "canon", "status"):
        sp.add_parser(c)
    s = sp.add_parser("approve-canon")
    s.add_argument("--sha", required=True)
    s = sp.add_parser("write")
    s.add_argument("n")
    s.add_argument("--mode", choices=["team", "aion", "plot"], default="team")
    s = sp.add_parser("plot")
    s.add_argument("n")
    s = sp.add_parser("judge")
    s.add_argument("n")
    s.add_argument("--a", choices=["team", "plot"], default="team")
    s.add_argument("--raw", action="store_true")
    for c in ("proofread", "proofread-apply", "polish", "polish-apply"):
        s = sp.add_parser(c)
        s.add_argument("n")
        s.add_argument("--mode", choices=["team", "aion", "plot"], default="team")
        if c == "proofread":
            s.add_argument("--auto", action="store_true")
    a = ap.parse_args()
    guard_stop()
    {"ping": cmd_ping, "canon": cmd_canon, "approve-canon": cmd_approve, "write": cmd_write,
     "judge": cmd_judge, "status": cmd_status,
     "proofread": cmd_proofread, "proofread-apply": cmd_proofread_apply,
     "plot": cmd_plot, "polish": cmd_polish, "polish-apply": cmd_polish_apply}[a.cmd](a)


if __name__ == "__main__":
    main()
