import json, glob, re, collections
from pathlib import Path
H=Path(__file__).parent; R=H/"report"; R.mkdir(exist_ok=True)
MAIN=["マスター","エーリカ","ザザ","ダリオ","リナ","ブリギッテ","マグダ","トマス","アガタ","ロズモンド","バルタザール","ヴェイ","ハク","チィ","ヴィルマ","パウル","ブラント","ホルン","アルブレヒト","ルル","シグ","ニコ","イゾルデ","エルノ","ドゥン","ヘルマン","グレタ","ヨーナス","ゴルム"]
PLACES=["錆び釘亭","二階","書庫","組合長の部屋","厩","中庭","裏口","カウンター","詰所","大聖堂","市参事会館","裁きの間","北門","南門","下の谷","ロズモンド館","黒猫の尾","北街道","ネーベル"]
def canon(name, aliases):
    s=" ".join([name]+aliases)
    if "俺" in name and "マスター" not in s: return "マスター"
    for m in MAIN:
        if m in name: return m
    for m in MAIN:
        if m in s: return m
    return name
C=collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(set)))
P=collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(set)))
flags=[]
for f in sorted(glob.glob(str(H/"out/ep*.json"))):
    tag=Path(f).stem; ep=tag[2:4]
    try: d=json.load(open(f,encoding="utf-8"))
    except Exception as e: print("bad",f,e); continue
    for c in d.get("characters",[]):
        n=canon(c.get("name",""), c.get("aliases",[]) or [])
        for x in c.get("first_person",[]) or []: C[n]["一人称"][ep].add(f'{x.get("word")}')
        for x in c.get("calls_others",[]) or []: C[n]["呼び方"][ep].add(f'{x.get("target")}→{x.get("word")}')
        for x in c.get("speech",[]) or []: C[n]["口調"][ep].add(f'{x.get("feature")}「{x.get("example","")}」{x.get("ref","")}@{tag}')
        for x in c.get("looks",[]) or []: C[n]["外見"][ep].add(f'{x.get("feature")} {x.get("ref","")}@{tag}')
        for x in c.get("traits",[]) or []: C[n]["性格"][ep].add(f'{x.get("feature")}')
        for x in c.get("whereabouts",[]) or []: C[n]["所在"][ep].add(f'{x.get("when")}｜{x.get("where")}｜{x.get("doing")} {x.get("ref","")}@{tag}')
    for p in d.get("places",[]):
        nm=p.get("name","")
        key=next((k for k in PLACES if k in nm), nm)
        for fld,lab in (("layout","配置"),("scenery","情景"),("weather_season","天気季節")):
            for x in p.get(fld,[]) or []: P[key][lab][ep].add(f'[{nm}] {x.get("feature")} {x.get("ref","")}@{tag}')
    for x in d.get("season_mismatch",[]) or []: flags.append(f'- 季節 ep{ep} {tag}: {x.get("text")}（{x.get("why")}）{x.get("ref")}')
    for x in d.get("inner_inconsistencies",[]) or []: flags.append(f'- 話内 ep{ep} {tag}: {x.get("text")} {x.get("refs")}')
def dump(D, fn, fields):
    out=[]
    for n in sorted(D, key=lambda k: -sum(len(v) for fv in D[k].values() for v in fv.values())):
        out.append(f"\n## {n}")
        for fld in fields:
            if fld not in D[n]: continue
            out.append(f"### {fld}")
            for ep in sorted(D[n][fld]): out.append(f"- {ep}: " + " ／ ".join(sorted(D[n][fld][ep])))
    (R/fn).write_text("\n".join(out),encoding="utf-8")
dump(C,"characters_full.md",["一人称","呼び方","口調","外見","性格","所在"])
# compact: first person / calls / speech only, main chars
comp=[]
for n in MAIN:
    if n not in C: continue
    comp.append(f"\n## {n}")
    for fld in ["一人称","呼び方"]:
        if fld in C[n]: comp.append(f"### {fld}\n"+"\n".join(f"- {ep}: "+" ／ ".join(sorted(C[n][fld][ep])) for ep in sorted(C[n][fld])))
(R/"characters_voice.md").write_text("\n".join(comp),encoding="utf-8")
dump(P,"places_full.md",["配置","情景","天気季節"])
(R/"flags.md").write_text("\n".join(flags),encoding="utf-8")
import os
for fn in os.listdir(R): print(fn, os.path.getsize(R/fn))
print("chars:",len(C),"places:",len(P),"flags:",len(flags))
