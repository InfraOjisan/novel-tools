あなたは厳格な整合の検査役です。下の「原稿（第{{N}}章）」を、CANON・LEDGER・BRIEF 共通ルールに照らして検査してください。好みではなく、**破綻の有無**だけを見ます。

# 検査項目
- canon：CANON の不変条件・固有名詞と数値・呼び方・語りの形に反する
- ledger：LEDGER の事実と食い違う
- rule：BRIEF の機能・禁止・糸の操作（設置/補強/回収の過不足、早すぎる回収）に反する
- validity：そもそも成り立つか（時刻の矛盾、移動時間、季節・天気、物理的にありえない動き、金額の出どころ）

# 出力（JSON のみ）
{"issues":[{"severity":"high|low","kind":"canon|ledger|rule|validity","quote_draft":"原稿からそのまま写した40字以内の引用","source":"CANON|LEDGER|BRIEF|なし","quote_source":"その資料からそのまま写した40字以内の引用（validity は空でよい）","explain":"何がどう食い違うか（100字以内）"}]}
- 引用は一字一句そのまま。照合に通らない指摘は採用されない。
- 問題がなければ {"issues":[]}。high は「この章を書き直さないと正典が壊れる」ものだけ。
