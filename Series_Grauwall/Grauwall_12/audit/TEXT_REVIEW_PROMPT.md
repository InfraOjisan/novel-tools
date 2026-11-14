# 本文審査の依頼：グラウヴァル第12回『十三個目の卵』（全16章）

あなたは、この本文を書いていない審査役です。`Series_Grauwall/Grauwall_12/chapters/ch01.md`〜`ch16.md` を、設計書と既刊に照らして審査してください。褒める必要はありません。指摘だけを返してください。

## 守ること
- **ファイルは一切変更しない・作らない。** 読むだけ。結果は標準出力にだけ書く。
- 指摘には必ず根拠（ファイル名と行番号、短い引用）を付ける。根拠が見つからないものは「疑問」の欄へ。
- 検索するときは、ファイルかフォルダのパスをそのまま指定する。

## 読むもの
- 本文：`Series_Grauwall/Grauwall_12/chapters/`（フォルダ）
- 設計：`Series_Grauwall/Grauwall_12/BRIEF.md`、`Series_Grauwall/Grauwall_12/canon/CANON.md`
- 正典：`Series_Grauwall/SERIES_BIBLE.md`（v1.32）、`Series_Grauwall/SERIES_LEDGER.md`
- 既刊（必要な箇所を検索）：`Series_Grauwall/Grauwall_01/output/final.md`、`Series_Grauwall/Grauwall_05/output/final.md`、`Series_Grauwall/Grauwall_10/output/final_proofread.md`（三〇二年の裁きの場面）、`Series_Grauwall/Grauwall_11/output/final_proofread.md`

## 点検の項目
1. canon：CANON の一字一句の台詞・帳面・判例・依頼票が、そのまま入っているか。数値（換えの値、三百枚、百枚、助成六十枚、卵十二個、銅貨二枚）。日付と鐘。
2. consistency：既刊との矛盾。とくに第10回の三〇二年の裁きの描写（申し立ての言葉、アガタの証言、ザザの答え、裁き役の言葉）。
3. invariants：CANON 第9節の不変条件（紅玉の行方、「石だ」と言わない、マスターは三一三年の章で台詞の嘘をつかない、夫人の言葉の真偽を地の文で書かない、第15章で名・性別の代名詞・隊長だったことを書かない、第16章の頭巾の男の名・種族・探しものを書かない、ほか）。
4. viewpoint：視点人物が見聞きできないことを地の文に書いていないか（マスターの章、アガタの章、マグダの章、第15章は内心なし、第16章は内心一か所）。
5. fairness：第15章の「マスター」が誰かを、第15章より前の手がかりだけで読者が推せるか。
6. logic：人物の行動原理と行動が合っているか。仕掛けに無理がないか。
7. japanese：係り受けのあいまいな文、「の」の三連続、初出の呼び名に「誰の、何か」が添えてあるか、主語の取り違え。
8. length：各章3,000字以内（第9章は3,500字以内）。

## 出力の形式
```
# 本文審査（モデル名：＿＿＿）

## 指摘
| # | 重さ | 項目 | 章・行 | 中身 | 根拠（引用） | 直し方の案 |
|---|---|---|---|---|---|---|
（重さ：高＝正典・既刊・不変条件に反する／中＝視点・論理・設計の内部矛盾／低＝日本語・読みやすさ）

## 疑問
- …

## 総評（三行以内）
```

結果は `Series_Grauwall/Grauwall_12/audit/text_review_luna.md` に、**プロデューサーが**保存する。
