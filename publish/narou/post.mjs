#!/usr/bin/env node
// 小説家になろう 投稿自動化 (Playwright + 手元のGoogle Chrome)
//
//   node post.mjs login                       初回のみ。開いたChromeで人間がログインする
//   node post.mjs status  <Novel_N>           なろう側の話一覧(下書き/投稿済)とローカルの差分
//   node post.mjs draft   <Novel_N> [--only=3] [--dry-run]   未登録の話を下書き保存(公開しない)
//   node post.mjs verify  <Novel_N>           下書きの本文・サブタイトルがローカルと完全一致か検証
//   node post.mjs publish <Novel_N> [--only=3] --yes          下書きを話数順に公開(人間のOKが必要)
//   node post.mjs check   <Novel_N>           公開済み話の読者向けページ本文をローカルと照合
//
// 共通: --headless  画面を出さない / 既定はChromeを表示して実行
// 認証: パスワードは扱わない。専用プロファイル(.chrome-profile)にログイン状態を保存して再利用する。
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROFILE = process.env.NAROU_PROFILE || path.join(HERE, '.chrome-profile');
const BASE = 'https://syosetu.com';
const args = process.argv.slice(2);
const cmd = args[0];
const workName = args.find((a, i) => i > 0 && !a.startsWith('--'));
const flag = (n) => args.includes(`--${n}`);
const opt = (n) => (args.find((a) => a.startsWith(`--${n}=`)) || '').split('=')[1];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

function loadWork(name) {
  if (!name) die('作品名(Novel_1 など)を指定してください');
  const works = JSON.parse(fs.readFileSync(path.join(HERE, 'works.json'), 'utf8'));
  const w = works.works[name];
  if (!w) die(`works.json に ${name} がありません`);
  if (!w.narou_novel_id) die(`${name} の narou_novel_id が未設定です`);
  const mdir = path.join(HERE, 'out', name);
  if (!fs.existsSync(path.join(mdir, 'manifest.json'))) die('out/ がありません。先に python3 prepare.py を実行してください');
  const manifest = JSON.parse(fs.readFileSync(path.join(mdir, 'manifest.json'), 'utf8'));
  const episodes = manifest.episodes.map((e) => ({ ...e, body: fs.readFileSync(path.join(mdir, e.file), 'utf8') }));
  return { name, id: w.narou_novel_id, title: w.title, episodes };
}
function die(msg) { console.error('ERROR:', msg); process.exit(2); }

const STATE_DIR = path.join(HERE, 'state');
function saveState(work, patch) {
  fs.mkdirSync(STATE_DIR, { recursive: true });
  const f = path.join(STATE_DIR, `${work}.json`);
  const cur = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : { work, episodes: {} };
  Object.assign(cur.episodes, patch);
  cur.updated = new Date().toISOString();
  fs.writeFileSync(f, JSON.stringify(cur, null, 2));
}

async function launch() {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome', headless: flag('headless'), viewport: { width: 1280, height: 900 }, locale: 'ja-JP',
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  page.setDefaultTimeout(30000);
  return { ctx, page };
}

async function isLoggedIn(page) {
  await page.goto(`${BASE}/usernovel/list/`, { waitUntil: 'domcontentloaded' });
  return (await page.locator('a[href*="/login/logout/"]').count()) > 0;
}
async function requireLogin(page) {
  if (!(await isLoggedIn(page))) die('ログインされていません。 node post.mjs login を実行し、開いたChromeで人間がログインしてください');
}

// 管理画面の話一覧(下書き/投稿済)を全ページ分取得
async function listEpisodes(page, id) {
  const out = [];
  for (const filter of ['draft', 'posted']) {
    let url = `${BASE}/usernovelmanage/top/ncode/${id}/` + (filter === 'draft' ? '?filter=draft' : '');
    for (let guard = 0; guard < 20 && url; guard++) {
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      const items = await page.$$eval('.p-up-episode-item', (els) => els.map((el) => {
        const a = el.querySelector('.p-up-episode-item__title a');
        const label = a?.querySelector('.c-up-label')?.textContent.trim() || '';
        const btn = el.querySelector('[data-draftepisodeid]');
        return { subtitle: (a?.textContent || '').replace(label, '').replace(/ /g, ' ').trim(), label, href: a?.href || '', draftId: btn?.dataset.draftepisodeid || (a?.href.match(/draftepisodeid\/(\d+)/) || [])[1] || null };
      }));
      for (const it of items) out.push({ ...it, kind: it.label.includes('下書き') ? 'draft' : 'posted' });
      url = await page.$eval('a[rel="next"], .c-pager__item--next a, a.c-pager__link--next', (a) => a.href).catch(() => null);
    }
  }
  const seen = new Set();
  return out.filter((e) => (seen.has(e.kind + e.subtitle) ? false : seen.add(e.kind + e.subtitle)));
}

async function cmdLogin() {
  const { ctx, page } = await launch();
  await page.goto(`${BASE}/login/input/`);
  log('開いたChromeでなろうにログインしてください(最大10分待ちます)。パスワードはスクリプトでは扱いません。');
  const t0 = Date.now();
  while (Date.now() - t0 < 600000) {
    await sleep(3000);
    try { if (!page.url().includes('/login/') ) break; } catch { /* navigating */ }
  }
  const ok = await isLoggedIn(page);
  log(ok ? 'ログイン確認OK。以降は --headless でも実行できます' : 'ログインを確認できませんでした');
  await ctx.close();
  process.exit(ok ? 0 : 1);
}

async function cmdStatus(w, page) {
  const remote = await listEpisodes(page, w.id);
  const bySub = new Map(remote.map((r) => [r.subtitle, r]));
  console.log(`== ${w.name} 「${w.title}」 なろう側 ${remote.length}話 / ローカル ${w.episodes.length}話`);
  for (const e of w.episodes) {
    const r = bySub.get(e.subtitle);
    console.log(`  ${String(e.seq).padStart(3, '0')} ${e.subtitle.padEnd(18, '　')} ${r ? (r.kind === 'draft' ? '下書き済' : '投稿済') : '未登録'}`);
  }
  const extra = remote.filter((r) => !w.episodes.some((e) => e.subtitle === r.subtitle));
  if (extra.length) console.log('  !! ローカルに無い話:', extra.map((r) => r.subtitle).join(' / '));
  return remote;
}

async function draftOne(page, w, ep) {
  await page.goto(`${BASE}/draftepisode/input/ncode/${w.id}/`, { waitUntil: 'domcontentloaded' });
  await page.fill('input[name=subtitle]', ep.subtitle);
  await page.fill('textarea[name=novel]', ep.body);
  await sleep(500);
  const counter = await page.locator('body').innerText();
  const m = counter.match(/文字数（空白・改行含む）：([\d,]+)字/);
  if (m && Number(m[1].replace(/,/g, '')) !== ep.body.length) throw new Error(`文字数カウンタ不一致 画面${m[1]} / ローカル${ep.body.length}`);
  await Promise.all([
    page.waitForURL(/draftepisode\/view\/draftepisodeid\/\d+/, { timeout: 60000 }),
    page.locator('input[type=submit][value="下書き保存"]').first().click(),
  ]);
  const draftId = page.url().match(/draftepisodeid\/(\d+)/)[1];
  return draftId;
}

async function readDraft(page, draftId) {
  await page.goto(`${BASE}/draftepisode/updateinput/draftepisodeid/${draftId}/`, { waitUntil: 'domcontentloaded' });
  const subtitle = await page.inputValue('input[name=subtitle]');
  const body = (await page.inputValue('textarea[name=novel]')).replace(/\r\n/g, '\n');
  return { subtitle, body };
}

async function cmdDraft(w, page) {
  const only = opt('only') ? Number(opt('only')) : null;
  const remote = await listEpisodes(page, w.id);
  const have = new Set(remote.map((r) => r.subtitle));
  for (const ep of w.episodes) {
    if (only && ep.seq !== only) continue;
    if (have.has(ep.subtitle)) { log(`skip ${ep.seq} ${ep.subtitle} (登録済)`); continue; }
    if (flag('dry-run')) { log(`[dry-run] 下書き保存予定 ${ep.seq} ${ep.subtitle} ${ep.body.length}字`); continue; }
    const draftId = await draftOne(page, w, ep);
    const got = await readDraft(page, draftId);
    const ok = got.subtitle === ep.subtitle && got.body.trim() === ep.body.trim();
    saveState(w.name, { [ep.seq]: { subtitle: ep.subtitle, draftId, status: ok ? 'draft_verified' : 'draft_MISMATCH' } });
    log(`${ok ? 'OK ' : 'NG '} 下書き保存 ${ep.seq} ${ep.subtitle} draftId=${draftId}`);
    if (!ok) die(`保存内容がローカルと一致しません (seq ${ep.seq})。手動で確認してください`);
    await sleep(2000);
  }
}

async function cmdVerify(w, page) {
  const remote = await listEpisodes(page, w.id);
  let bad = 0;
  for (const ep of w.episodes) {
    const r = remote.find((x) => x.subtitle === ep.subtitle && x.kind === 'draft');
    if (!r) { console.log(`  ${ep.seq} ${ep.subtitle}: 下書きなし(未登録か投稿済み)`); continue; }
    const got = await readDraft(page, r.draftId);
    const ok = got.body.trim() === ep.body.trim();
    if (!ok) bad++;
    console.log(`  ${ep.seq} ${ep.subtitle}: ${ok ? '一致' : '不一致!'} (${got.body.trim().length}字 / ローカル${ep.body.trim().length}字)`);
    await sleep(800);
  }
  if (bad) process.exit(1);
}

async function publishOne(page, draftId, subtitle) {
  await page.goto(`${BASE}/draftepisode/view/draftepisodeid/${draftId}/`, { waitUntil: 'domcontentloaded' });
  await page.locator('a.js-post_input_button').first().click();
  await page.locator('#reserve-off').waitFor({ state: 'visible' });
  await page.locator('#reserve-off').check();               // 予約掲載は使わない(即時公開)
  await page.getByRole('button', { name: /投稿\[確認\]/ }).click();
  // 同じモーダル内で「投稿[実行]」に切り替わる(画面遷移なし)。押すと「投稿が完了しました」が出る
  const exec = page.getByRole('button', { name: /投稿\[実行\]/ });
  await exec.waitFor({ state: 'visible', timeout: 20000 });
  await exec.click();
  await page.getByText('投稿が完了しました').waitFor({ state: 'visible', timeout: 30000 });
}

async function cmdPublish(w, page) {
  if (!flag('yes')) die('公開は取り消しにくい操作です。内容確認後、人間のOKを得てから --yes を付けて実行してください');
  const only = opt('only') ? Number(opt('only')) : null;
  for (const ep of w.episodes) {
    if (only && ep.seq !== only) continue;
    const remote = await listEpisodes(page, w.id);
    if (remote.some((r) => r.subtitle === ep.subtitle && r.kind === 'posted')) { log(`skip ${ep.seq} ${ep.subtitle} (投稿済)`); continue; }
    const d = remote.find((r) => r.subtitle === ep.subtitle && r.kind === 'draft');
    if (!d) die(`下書きがありません: ${ep.subtitle}。先に draft を実行してください`);
    const got = await readDraft(page, d.draftId);
    if (got.body.trim() !== ep.body.trim()) die(`下書きがローカルと不一致のため公開を中止: ${ep.subtitle}`);
    await publishOne(page, d.draftId, ep.subtitle);
    const after = await listEpisodes(page, w.id);
    const ok = after.some((r) => r.subtitle === ep.subtitle && r.kind === 'posted');
    saveState(w.name, { [ep.seq]: { subtitle: ep.subtitle, draftId: d.draftId, status: ok ? 'published' : 'publish_UNCONFIRMED' } });
    log(`${ok ? 'OK ' : 'NG '} 公開 ${ep.seq} ${ep.subtitle}`);
    if (!ok) die(`公開を確認できませんでした (seq ${ep.seq})`);
    await sleep(3000);
  }
}

// 管理画面の作品ページから、読者向けのNコードを取得する
async function getNcode(page, id) {
  await page.goto(`${BASE}/usernovelmanage/top/ncode/${id}/`, { waitUntil: 'domcontentloaded' });
  const href = await page.$$eval('a', (as) => (as.map((a) => a.href).find((h) => /ncode\.syosetu\.com\/n\w+\/?$/.test(h)) || ''));
  const m = href.match(/ncode\.syosetu\.com\/(n\w+)/);
  return m ? m[1] : null;
}

// 公開後の照合: 読者向けページ(https://ncode.syosetu.com/<Nコード>/<話数>/)の本文をローカルと比較
async function cmdCheck(w, page) {
  const ncode = await getNcode(page, w.id);
  if (!ncode) { console.log('Nコードを取得できません(まだ1話も公開されていない可能性)'); process.exit(1); }
  console.log(`== ${w.name} ${ncode}  https://ncode.syosetu.com/${ncode}/`);
  const remote = (await listEpisodes(page, w.id)).filter((r) => r.kind === 'posted');
  let bad = 0;
  for (const ep of w.episodes) {
    if (!remote.some((x) => x.subtitle === ep.subtitle)) { console.log(`  ${ep.seq} ${ep.subtitle}: 未公開`); bad++; continue; }
    const url = `https://ncode.syosetu.com/${ncode}/${ep.seq}/`;
    const p = await page.context().newPage();
    await p.goto(url, { waitUntil: 'domcontentloaded' });
    const got = await p.evaluate(() => {
      const el = document.querySelector('.js-novel-text.p-novel__text:not(.p-novel__text--preface):not(.p-novel__text--afterword)');
      return { body: el ? el.innerText : '', title: document.querySelector('.p-novel__title')?.innerText || '' };
    });
    const norm = (s) => s.replace(/\s+/g, '');
    const okBody = got.body && norm(got.body) === norm(ep.body);
    const okTitle = norm(got.title) === norm(ep.subtitle);
    if (!okBody || !okTitle) bad++;
    console.log(`  ${ep.seq} ${ep.subtitle}: ${okBody && okTitle ? '一致' : '不一致!'} ${url}`);
    await p.close();
    await sleep(800);
  }
  if (bad) process.exit(1);
}

(async () => {
  if (cmd === 'login') return cmdLogin();
  if (!['status', 'draft', 'verify', 'publish', 'check'].includes(cmd)) {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n').slice(1, 12).join('\n').replace(/^\/\/ ?/gm, ''));
    process.exit(cmd ? 2 : 0);
  }
  const w = loadWork(workName);
  const { ctx, page } = await launch();
  try {
    await requireLogin(page);
    if (cmd === 'status') await cmdStatus(w, page);
    if (cmd === 'draft') await cmdDraft(w, page);
    if (cmd === 'verify') await cmdVerify(w, page);
    if (cmd === 'publish') await cmdPublish(w, page);
    if (cmd === 'check') await cmdCheck(w, page);
  } finally {
    await ctx.close();
  }
})().catch((e) => { console.error('FAILED:', e.message); process.exit(1); });
