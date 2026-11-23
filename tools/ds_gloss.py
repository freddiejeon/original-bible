"""딥시크(오픈라우터)로 새 표제어의 한국어 뜻풀이 초안을 만듦.

build_data.py를 실행한 뒤 쓴다. _missing.txt의 표제어 중 glosses_ko.json에 없는 것만 보낸다.

  python ds_gloss.py --dry-run     # 첫 묶음의 요청 내용만 보여 줌 (키·비용 없음)
  python ds_gloss.py               # 초안 작성 → _gloss_draft.json, 점검 목록 → _gloss_review.txt
  python ds_gloss.py --merge       # 점검을 마친 초안을 glosses_ko.json 끝에 붙임

키: .secrets/openrouter_key.txt 또는 환경 변수 OPENROUTER_API_KEY.
보내는 내용은 공개 본문의 표제어·사전 뜻·절 본문뿐이다.
"""
import argparse
import json
import os
import random
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GLOSS_PATH = HERE / 'glosses_ko.json'
MISSING_PATH = HERE / '_missing.txt'
DRAFT_PATH = HERE / '_gloss_draft.json'
REVIEW_PATH = HERE / '_gloss_review.txt'
PARTS_DIR = ROOT / 'build' / 'parts'
KEY_PATH = ROOT / '.secrets' / 'openrouter_key.txt'
API_URL = 'https://openrouter.ai/api/v1/chat/completions'

RULES = """너는 성경 원어(히브리어·아람어·헬라어) 사전의 한국어 뜻풀이를 쓴다.
각 표제어에 대해 스트롱 사전 뜻, KJV 번역어, 처음 나오는 절(개역한글·KJV)을 받는다.

규칙:
- 짧게 쓴다. 뜻이 여럿이면 쉼표로 2~3개까지. 설명문을 쓰지 않는다.
- 동사는 기본형 "~다"로 쓴다 (예: 거두다, 치다, 두드리다).
- 고유명사는 반드시 주어진 개역한글 절에 나오는 표기를 그대로 쓴다. 절에서 찾을 수 없으면 끝에 ?를 붙인다.
- 일반 낱말은 스트롱 사전 뜻과 KJV 번역어를 기준으로 쓰고, 개역한글 절은 낱말 선택의 참고로만 쓴다.
  절에 나온 활용형(우매한, 아니, 치니)을 그대로 옮기지 말고 사전 형태로 쓴다:
  명사는 명사(어리석음), 형용사·동사는 "~다"(어리석다), 부사·조사는 기존 예시처럼(~도 아니다, ~에게).
- 뜻이 좁으면 좁은 뜻을 살린다 (소고를 치다 ○, 치다 ×).
- 확신이 없으면 끝에 ?를 붙인다.
- "헬라어", "히브리어" 같은 언어 이름은 넣지 않는다.
- 출력은 JSON 객체 하나: {"스트롱 번호": "뜻풀이", ...}. 받은 번호를 모두, 그 번호만 쓴다."""


def load_gloss():
    return json.loads(GLOSS_PATH.read_text(encoding='utf-8'))


def load_missing(gloss):
    out = []
    for line in MISSING_PATH.read_text(encoding='utf-8').splitlines():
        sid = line.split(' ', 1)[0].strip()
        if sid and sid not in gloss:
            out.append(sid)
    return out


def index_parts():
    """스트롱 번호별 사전 항목과 처음 나오는 절."""
    lex, first = {}, {}
    for f in sorted(PARTS_DIR.glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        for sid, e in d.get('lex', {}).items():
            lex.setdefault(sid, e)
        for ch in d['chapters']:
            for v in ch['verses']:
                for w in v.get('w', []):
                    for s in w.get('segs', []):
                        sid = s.get('sid')
                        if sid and sid not in first:
                            first[sid] = {'ref': f"{ch['id']} {v['n']}절", 'pos': s.get('pos', ''),
                                          'word': s.get('x', ''), 'ko': v.get('ko', ''), 'en': v.get('en', '')}
    return lex, first


def item_for(sid, lex, first):
    e, o = lex.get(sid, {}), first.get(sid, {})
    return {'id': sid, 'lemma': e.get('lemma', ''), 'def': e.get('def', ''), 'kjv': e.get('kjv', ''),
            'pos': o.get('pos', ''), 'ref': o.get('ref', ''), 'word': o.get('word', ''),
            'ko_verse': o.get('ko', ''), 'en_verse': o.get('en', '')}


def examples(gloss, n=30):
    rnd = random.Random(7)
    keys = rnd.sample(sorted(gloss), min(n, len(gloss)))
    return '\n'.join(f'{k}: {gloss[k]}' for k in keys)


def build_messages(items, gloss):
    system = RULES + '\n\n기존 뜻풀이 예시 (이 말투를 따른다):\n' + examples(gloss)
    user = json.dumps(items, ensure_ascii=False, indent=1)
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def read_key():
    key = os.environ.get('OPENROUTER_API_KEY') or (KEY_PATH.read_text(encoding='utf-8').strip() if KEY_PATH.exists() else '')
    if not key:
        sys.exit(f'키가 없음: {KEY_PATH} 에 넣거나 OPENROUTER_API_KEY 를 설정')
    return key


def call(messages, model, key):
    body = json.dumps({'model': model, 'messages': messages, 'temperature': 0.2,
                       'response_format': {'type': 'json_object'}}).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'X-Title': 'original-bible-gloss'})
    with urllib.request.urlopen(req, timeout=300) as r:
        res = json.loads(r.read().decode('utf-8'))
    text = res['choices'][0]['message']['content'].strip()
    if text.startswith('```'):
        text = text.strip('`').removeprefix('json').strip()
    return json.loads(text), res.get('usage', {})


def has_hangul(s):
    return any('가' <= c <= '힣' for c in s)


def review_notes(sid, ko, it):
    notes = []
    if ko.endswith('?'):
        notes.append('확신 없음')
    if it['pos'] == '고유명사' and not any(p.strip(' ?') and p.strip(' ?') in it['ko_verse'] for p in ko.split(',')):
        notes.append('고유명사가 개역한글 절에 없음')
    if it['pos'] == '명사' and ko.rstrip(' ?').endswith('다'):
        notes.append('명사인데 ~다로 끝남')
    return notes


def write_review(draft, items_by_id):
    lines = []
    for sid, ko in draft.items():
        it = items_by_id.get(sid)
        if not it:
            continue
        notes = review_notes(sid, ko, it)
        if notes:
            lines.append(f"{sid} {it['lemma']} → {ko}  [{', '.join(notes)}]  {it['ref']}: {it['ko_verse']}")
    REVIEW_PATH.write_text('\n'.join(lines), encoding='utf-8')
    return len(lines)


def merge():
    gloss = load_gloss()
    draft = json.loads(DRAFT_PATH.read_text(encoding='utf-8'))
    bad = [k for k, v in draft.items() if v.endswith('?')]
    if bad:
        sys.exit(f'?가 남은 항목 {len(bad)}개를 먼저 고칠 것: {", ".join(bad[:10])}')
    new = {k: v for k, v in draft.items() if k not in gloss}
    gloss.update(new)
    GLOSS_PATH.write_text('{\n' + ',\n'.join(f'{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}'
                                            for k, v in gloss.items()) + '\n}', encoding='utf-8')
    print(f'{len(new)}개를 glosses_ko.json에 붙임 (전체 {len(gloss)}개)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--merge', action='store_true')
    ap.add_argument('--batch', type=int, default=60)
    ap.add_argument('--model', default='deepseek/deepseek-chat')
    a = ap.parse_args()
    if a.merge:
        return merge()

    gloss = load_gloss()
    draft = json.loads(DRAFT_PATH.read_text(encoding='utf-8')) if DRAFT_PATH.exists() else {}
    lex, first = index_parts()
    todo = [s for s in load_missing(gloss) if s not in draft]
    items = [item_for(s, lex, first) for s in todo]
    items_by_id = {it['id']: it for it in items}
    print(f'보낼 표제어 {len(items)}개, 묶음 {-(-len(items) // a.batch)}개')
    if not items:
        return
    if a.dry_run:
        for m in build_messages(items[:a.batch], gloss):
            print(f"--- {m['role']} ---\n{m['content'][:3000]}")
        return

    key = read_key()
    tokens_in = tokens_out = 0
    for i in range(0, len(items), a.batch):
        chunk = items[i:i + a.batch]
        want = {it['id'] for it in chunk}
        got, usage = call(build_messages(chunk, gloss), a.model, key)
        tokens_in += usage.get('prompt_tokens', 0)
        tokens_out += usage.get('completion_tokens', 0)
        ok = {k: v.strip() for k, v in got.items() if k in want and isinstance(v, str) and has_hangul(v)}
        draft.update(ok)
        DRAFT_PATH.write_text(json.dumps(draft, ensure_ascii=False, indent=0), encoding='utf-8')
        print(f'묶음 {i // a.batch + 1}: {len(ok)}/{len(chunk)}개, 빠진 것: {sorted(want - set(ok))[:10]}')

    all_items = {**items_by_id, **{s: item_for(s, lex, first) for s in draft if s not in items_by_id}}
    n = write_review(draft, all_items)
    print(f'초안 {len(draft)}개 → {DRAFT_PATH.name}, 점검할 항목 {n}개 → {REVIEW_PATH.name}')
    print(f'토큰: 입력 {tokens_in}, 출력 {tokens_out}')


if __name__ == '__main__':
    main()
