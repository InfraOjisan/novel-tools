# 小説家になろう 投稿手順書(Goose / Hermes / 人間 共通)

対象: `Novel_N/output/` の完成原稿(md) → なろうへ **下書き保存 → 検証 → 公開 → 公開後照合**。
スクリプト: `prepare.py`(md→章テキスト)と `post.mjs`(ブラウザ操作)。どれも繰り返し実行しても二重投稿しない作りです(サブタイトルで登録済みを判定)。

## 守ること(エージェント向け)
1. **パスワードは入力しない・.envのIDやパスワードをスクリプトに渡さない。** ログインは人間が `node post.mjs login` で開いたChromeで一度だけ行う。
2. **公開(`publish`)は人間の明示的なOKの後にだけ実行する。** それ以外は下書き保存まで。
3. **AI利用状況は「直接使用」で申告済み**(2026-10-01、本人承認)。変更しない。
4. 作品削除・アカウント設定の変更はしない。
5. 想定外の画面・エラーが出たら中断して人間に報告する(リトライを繰り返さない)。

## 前提
- Mac: Node 22以上、Google Chrome、`cd publish/narou && npm install`(playwright-coreのみ。ブラウザのダウンロードは不要)
- `works.json` に作品ごとの `source`(投稿対象のmd)と `narou_novel_id`(管理画面URL `usernovelmanage/top/ncode/<ID>/` の数字)がある
- 現在の登録(2026-10-01 全話公開済み): Novel_1=管理ID 3332261 / Nコード n2594mv(銀の川をのぼる、校正済み版・全8話)、Novel_3=管理ID 3332262 / Nコード n2595mv(夜啼きの涙・全14話)
- 読者向けURL: https://ncode.syosetu.com/<Nコード>/<話数>/

## 通常フロー(作品ごと)
```bash
cd <repo>/publish/narou
git pull                              # 先に最新化(リポジトリ運用ルール)
python3 prepare.py Novel_3            # md → out/Novel_3/NNN.txt と manifest.json(5000字以内、場面区切り＊で前編/後編に分割)
python3 prepare.py --check            # 文字数・ハッシュの最終検証(NGなら中止)

node post.mjs login                   # 初回/セッション切れ時のみ。人間がChromeでログイン
node post.mjs status Novel_3          # なろう側の状況(未登録/下書き済/投稿済)
node post.mjs draft  Novel_3          # 未登録の話を下書き保存(保存後に内容をなろうから読み戻して完全一致を確認)
node post.mjs verify Novel_3          # 下書き全話の再検証
# ---- ここで人間に報告し、公開のOKを待つ ----
node post.mjs publish Novel_3 --yes   # 話数順に公開。公開ごとに一覧で確認
node post.mjs check  Novel_3          # 公開後、読者向けページの本文がローカルと一致するか照合
```
- 1話だけ試す: `--only=1`、実行せず確認: `draft --dry-run`、画面を出さない: `--headless`
- 途中で止まっても同じコマンドを再実行すれば続きから進む。
- 結果は `state/<作品>.json` に記録される(draftId・状態)。

## あらすじへの併載追記(Romancer)
Romancer 側の公開（docx 原稿のアップロード〜公開URLの記録）は `publish/romancer/RUNBOOK.md` を参照。公開URLは `works.json` の `romancer_url` に記録してから、ここを行う。

他サイトと重複掲載する場合、なろうの公式ヘルプ(外部サイトとの同時掲載について)により、**あらすじに重複投稿である旨を書く**必要がある。Romancerと併載する作品では、公開後に次の手順で追記する。

1. **RomancerのURLは、指示者が「なろう投稿の実行指示」と一緒に渡す。指定がない場合は、指示者に確認する**(URLを推測・省略して進めない。「Romancerには載せない」と回答があればこの工程は行わない)。
2. 作品設定の編集画面 `https://syosetu.com/usernovelmanage/updateinput/ncode/<管理ID>/` を開く(公開済み作品。下書き作品は `draftnovelmanage`)。
3. あらすじ欄(`#extext`)に `Romancer` が**すでに含まれていないか確認**する(含まれていれば追記しない。二重追記の防止)。
4. あらすじの末尾に、空行を1行あけて次の2行を追記する。`<URL>` は指示されたもの。
   ```
   ※この作品は「Romancer」（ボイジャー）にも重複して掲載しています。縦書き版はこちら。
   <URL>
   ```
5. 「編集[確認]」→ 確認画面の内容(特にあらすじ末尾のURLと、AI利用設定などの他項目が変わっていないこと)を見て →「編集[実行]」。
6. 読者向けページ `https://ncode.syosetu.com/<Nコード>/` を開き、あらすじに一文とURLが出ていることを確認し、結果を報告する。
- 注意: あらすじ内のURLは**クリックできない文字**として表示され、作品一覧側では途中が「…」で省略される(「続きを読む」で全体表示)。公式ヘルプにあらすじ欄のURLの可否は明記されていないため、保存できなくなった場合は「Romancerで『作品名』を検索」の一文に切り替えて指示者に報告する。
- 併載の事実が変わった場合(Romancer側を非公開にした等)は、一文を削除するか指示者に確認する。

## 終了条件(報告に含めること)
- `status` で全話が「投稿済」
- `check` が全話「一致」
- 作品ページURLと話数を人間に報告(Nコードは `check` の出力に出る)

## 公開後に人間が確認すること(スクリプトの対象外)
- 作品の「公開・受付設定」(感想・評価の受付、誤字報告)と完結設定
- 連載の更新間隔(予約掲載を使う場合は `reserve-on` と日時指定を手動で設定。現行スクリプトは即時公開のみ)

## 新しい作品を足すとき
1. `Novel_N/output/` に完成md(`## 第N章　題` 見出し形式)がある
2. なろうで「新しい作品を作成」(タイトルのみ→保存)し、作品設定でAI利用状況・ジャンル・あらすじ・キーワードを設定(下の画面メモ参照)
3. `works.json` に追記(`source`, `narou_novel_id`)
4. 通常フローを実行
5. Romancerにも載せる場合は「あらすじへの併載追記(Romancer)」を行う(URLの指示がなければ指示者に確認)

## トラブル対応
| 症状 | 対応 |
|---|---|
| `ログインされていません` | `node post.mjs login` を人間が実行 |
| `out/ がありません` | `python3 prepare.py` を先に実行 |
| `文字数カウンタ不一致` | 本文に特殊文字がある可能性。該当話の `out/…/NNN.txt` を確認して人間に報告 |
| `保存内容がローカルと一致しません` | 自動で直さず中断。人間が下書きを確認 |
| ツールの応答が途中で切れた | スクリプトは動き続けている場合がある。`ps` で `post.mjs` を確認し、終了後に `status` を見る(同じプロファイルは同時に2つ起動できない) |
| 公開後に `UNCONFIRMED` | 一覧(`status`)を再確認。二重公開を避けるため `publish` を急いで再実行しない |
| 画面構成が変わった | 下の「画面メモ」と照合してセレクタを更新 |

## 画面メモ(2026-10-01時点の実画面で確認)
- 作品作成: `/usernovel/input/`(タイトル→「保存する」)→ 作品ID発行 → `/draftnovelmanage/updateinput/ncode/<ID>/` で設定
  - AI利用状況 `aitype0〜3`(不使用/補助的利用/間接利用/直接使用)。未設定だと投稿不可
  - ジャンル `biggenre`(2=ファンタジー,4=SF…)→ `genre`(201=ハイファンタジー,402=宇宙…)、あらすじ `#extext`、キーワード `unique_keyword_array`(空白区切り)
- 話の新規作成: `/draftepisode/input/ncode/<ID>/` … `subtitle`(100字以内)、`novel`(200〜70,000字)、`preface`、`postscript`、submit「下書き保存」
- 下書き詳細: `/draftepisode/view/draftepisodeid/<ID>/` … 「投稿」→ モーダル(`reserve-off`/`reserve-on`、`_is_masterpiece`)→「投稿[確認]」→ 同じモーダル内で「投稿[実行]」→「投稿が完了しました」(画面遷移なし。2段階の確認がある)
- 読者向けページの本文: `.js-novel-text.p-novel__text`(前書き・後書きは別クラス)
- 話一覧: `/usernovelmanage/top/ncode/<ID>/`(投稿済)、`?filter=draft`(下書き)。行 `.p-up-episode-item`、タイトル `.p-up-episode-item__title a`
- 本文上限は70,000字。**5,000字はこちらの運用上の上限**(`works.json` の `limit_chars`)

## ブラウザ操作型エージェント(スクリプトが使えない場合の手動手順)
上の「画面メモ」のURLを順に開き、`out/<作品>/NNN.txt` の内容をサブタイトル(`manifest.json`)とともに貼り付けて「下書き保存」。保存後、編集画面で本文の文字数が一致することを確認する。公開は人間のOK後に「投稿」→「投稿[確認]」。
