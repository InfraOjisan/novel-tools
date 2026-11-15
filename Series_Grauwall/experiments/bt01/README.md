# bt01 — 第一作で「分岐の地図」の後ろ向き試験

第一作『夜啼きの涙』の本文だけをモデルに渡し、**物語を揺らせる箇所（分岐点）**を抽出させます。
正解は、公開後にプロデューサーと Claude が見つけた分岐点（設定資料の第7・9・10節）。本文は公開時から一字も変えていないので、「下読みのAIが、作者があとで気づいたことを先に出せるか」を測れます。

## 何を見るか

| 指標 | 意味 |
|---|---|
| G1 の順位 | 最大の分岐点「亡骸の身元を誰も確かめていない」を、何位に挙げたか |
| 重み付き再現率 | 正解8件（重み付き）のうち、いくつ当てたか |
| G1 の別値・芽 | 表の読み（ルルとシグ）以外の値を出したか。見分けの手がかり（片方のカフス、白い布）を拾ったか |
| 引用の正確さ | 引用が本文にそのままあるか（作話の検出） |
| 正解表に無い候補 | **ここが本命の収穫**。作者がまだ気づいていない分岐点かどうかを人が判定する |

正解表は `gold/GOLD.yaml`（作者のみ）。モデルには渡しません。

## 手順

```
# 1. 箱を作る（リポジトリの外に）
python3 Series_Grauwall/experiments/bt01/tools/make_box.py ~/Downloads/novel_studio/bt01_box

# 2. 箱の RUN.md に従い、各ハーネスを箱のフォルダで起動して依頼文を貼る
#    答えは results/<NAME>.json

# 3. 採点
python3 Series_Grauwall/experiments/bt01/tools/score.py ~/Downloads/novel_studio/bt01_box/results ~/Downloads/novel_studio/bt01_box/TEXT.md
#    → ~/Downloads/novel_studio/bt01_box/SCORE.md
```

## 対象のモデル

| ハーネス | モデル | 区分 |
|---|---|---|
| agy | Claude Sonnet 5.5 | ちょっと賢い |
| agy | Gemini 3.8 Flash | ちょっと賢い |
| Codex | GPT-6.1-Sol（high） | 賢い |
| OpenCodeGo | gpt-6-luna | 普通 |
| OpenCodeGo | claude-haiku-5-5 | 普通 |
| OpenCodeGo | mimo-v2.6-flash | 普通 |

Claude Opus 5.5（このセッション）は正解を知っているので、被験者に入れません。

## 注意

- 箱はリポジトリの外に置く。ハーネスが親フォルダをたどると `SERIES_BIBLE.md` の【秘密】（＝正解）が読めてしまう。`make_box.py` はリポジトリの中を指定すると止まる。
- 本文は約14万バイト。読み切れないモデルは、読み切れなかったこと自体を記録する。
- 採点の照合は語の一致による粗いもの。最後は人が `SCORE.md` を読んで判定する。
