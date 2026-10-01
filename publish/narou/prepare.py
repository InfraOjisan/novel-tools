#!/usr/bin/env python3
"""md(final.md) -> なろう投稿用テキスト(1話5000字以内)に変換する。標準ライブラリのみ。

使い方:
  python3 prepare.py                 # works.json の全作品を変換して out/ に出力
  python3 prepare.py Novel_1         # 作品を指定
  python3 prepare.py --check         # out/ が manifest と一致しているか検証(投稿前の最終確認)
出力:
  out/<作品>/NNN.txt   本文(WebUIの本文欄にそのまま貼る)
  out/<作品>/manifest.json  話ごとのサブタイトル・文字数・sha1
"""
import hashlib, json, math, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENE_BREAK = re.compile(r'^[＊*◇◆]{1,3}$')


def sha1(s): return hashlib.sha1(s.encode('utf-8')).hexdigest()


def parse_chapters(md):
    chapters, cur = [], None
    for line in md.splitlines():
        if line.startswith('## '):
            cur = {'heading': line[3:].strip(), 'lines': []}
            chapters.append(cur)
        elif line.startswith('# ') and cur is None:
            continue
        elif cur is not None:
            cur['lines'].append(line.rstrip())
    return chapters


def to_blocks(lines):
    """空行区切りの段落ブロック列にする。段落内の改行はそのまま保持。"""
    blocks, buf = [], []
    for l in lines:
        if l.strip() == '':
            if buf: blocks.append('\n'.join(buf)); buf = []
        else:
            buf.append(l)
    if buf: blocks.append('\n'.join(buf))
    return blocks


def join_blocks(blocks): return '\n\n'.join(blocks)


def split_blocks(blocks, limit):
    total = len(join_blocks(blocks))
    if total <= limit:
        return [blocks]
    k = math.ceil(total / limit)
    while True:
        # 累積文字数
        cum, run = [], 0
        for i, b in enumerate(blocks):
            run += len(b) + (2 if i else 0)
            cum.append(run)
        cuts = []  # 各ブロックの「直前で切る」インデックス
        prev = 0
        for part in range(1, k):
            target = total * part / k
            cands = [i for i in range(prev + 1, len(blocks) - (k - part))]
            scene = [i for i in cands if SCENE_BREAK.match(blocks[i].strip())]
            def dist(i): return abs(cum[i - 1] - target)
            # 場面区切りが目標位置の±20%内にあれば優先、なければ最寄りの段落境界
            pool = [i for i in scene if dist(i) <= total * 0.2 / k * k] or cands
            cuts.append(min(pool, key=dist))
            prev = cuts[-1]
        parts, s = [], 0
        for c in cuts + [len(blocks)]:
            parts.append(blocks[s:c]); s = c
        # 区切り記号は先頭/末尾から落とす
        parts = [[b for j, b in enumerate(p) if not (SCENE_BREAK.match(b.strip()) and (j == 0 or j == len(p) - 1))] for p in parts]
        if all(len(join_blocks(p)) <= limit for p in parts):
            return parts
        k += 1
        if k > 6:
            raise SystemExit('分割に失敗: 区切り可能な段落が足りません')


def part_suffix(i, n):
    if n == 1: return ''
    names = {2: ['前編', '後編'], 3: ['前編', '中編', '後編']}.get(n)
    return '（%s）' % (names[i] if names else '%d/%d' % (i + 1, n))


def build(name, cfg, limit):
    src = (HERE / cfg['source']).resolve()
    chapters = parse_chapters(src.read_text(encoding='utf-8'))
    outdir = HERE / 'out' / name
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob('*.txt'): old.unlink()
    episodes, seq = [], 0
    for ch in chapters:
        parts = split_blocks(to_blocks(ch['lines']), limit)
        for i, p in enumerate(parts):
            seq += 1
            body = join_blocks(p) + '\n'
            fn = '%03d.txt' % seq
            (outdir / fn).write_text(body, encoding='utf-8')
            subtitle = ch['heading'] + part_suffix(i, len(parts))
            episodes.append({'seq': seq, 'file': fn, 'subtitle': subtitle,
                             'chars': len(body.strip()), 'chars_no_newline': len(body.replace('\n', '')),
                             'sha1': sha1(body)})
    manifest = {'work': name, 'title': cfg['title'], 'source': cfg['source'],
                'limit_chars': limit, 'episodes': episodes}
    (outdir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def check(name, limit):
    outdir = HERE / 'out' / name
    m = json.loads((outdir / 'manifest.json').read_text(encoding='utf-8'))
    bad = []
    for e in m['episodes']:
        body = (outdir / e['file']).read_text(encoding='utf-8')
        if sha1(body) != e['sha1']: bad.append((e['seq'], 'sha1不一致'))
        if len(body.strip()) > limit: bad.append((e['seq'], '%d字 > %d' % (len(body.strip()), limit)))
        if len(e['subtitle']) > 100: bad.append((e['seq'], 'サブタイトルが100字超'))
    return m, bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cfg = json.loads((HERE / 'works.json').read_text(encoding='utf-8'))
    limit = cfg['limit_chars']
    names = args or list(cfg['works'])
    do_check = '--check' in sys.argv
    rc = 0
    for n in names:
        if do_check:
            m, bad = check(n, limit)
        else:
            m = build(n, cfg['works'][n], limit); m, bad = check(n, limit)
        print('== %s 「%s」 全%d話 (上限%d字)' % (n, m['title'], len(m['episodes']), limit))
        for e in m['episodes']:
            print('  %03d %-22s %5d字' % (e['seq'], e['subtitle'], e['chars']))
        if bad:
            rc = 1; print('  !! 問題:', bad)
    sys.exit(rc)


if __name__ == '__main__':
    main()
