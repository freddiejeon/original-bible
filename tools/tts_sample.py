"""Google Cloud TTS로 단어 20개 샘플을 만들어 build/samples/index.html로 들어 볼 수 있게 한다.

키는 .secrets/google_tts_key.txt 또는 환경 변수 GOOGLE_TTS_API_KEY에서 읽는다. 앱에는 키가 들어가지 않는다.
사용법: python tts_sample.py
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
KEY_FILE = ROOT / '.secrets' / 'google_tts_key.txt'
OUT = ROOT / 'build' / 'samples'
API = 'https://texttospeech.googleapis.com/v1/'
# (화면 표기, 읽힐 글자, 앱의 한글 발음). 하나님의 이름은 앱의 결정대로 아도나이로 읽힌다.
WORDS = [
    ('בְּרֵאשִׁית', 'בְּרֵאשִׁית', '베레쉬트'), ('בָּרָא', 'בָּרָא', '바라'), ('אֱלֹהִים', 'אֱלֹהִים', '엘로힘'), ('יְהוָה', 'אֲדֹנָי', '아도나이'),
    ('הַשָּׁמַיִם', 'הַשָּׁמַיִם', '하샤마임'), ('הָאָרֶץ', 'הָאָרֶץ', '하아레츠'), ('וַיֹּאמֶר', 'וַיֹּאמֶר', '바요메르'), ('אוֹר', 'אוֹר', '오르'),
    ('רוּחַ', 'רוּחַ', '루아흐'), ('מַיִם', 'מַיִם', '마임'), ('לַיְלָה', 'לַיְלָה', '라일라'), ('כָּל', 'כָּל', '콜'),
    ('אַבְרָהָם', 'אַבְרָהָם', '아브라함'), ('יִצְחָק', 'יִצְחָק', '이츠하크'), ('יַעֲקֹב', 'יַעֲקֹב', '야아코브'), ('יִשְׂרָאֵל', 'יִשְׂרָאֵל', '이스라엘'),
    ('חֶסֶד', 'חֶסֶד', '헤세드'), ('שָׁלוֹם', 'שָׁלוֹם', '샬롬'), ('וַיִּשְׁלַח', 'וַיִּשְׁלַח', '바이쉴라흐'), ('אָהֳלוֹ', 'אָהֳלוֹ', '오홀로'),
]


def call(key, path, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={'X-Goog-Api-Key': key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f'Google 오류 {e.code}: {json.load(e).get("error", {}).get("message", "")}')


def main():
    key = os.environ.get('GOOGLE_TTS_API_KEY') or (KEY_FILE.read_text(encoding='utf-8').strip() if KEY_FILE.exists() else '')
    if not key:
        sys.exit(f'키가 없습니다: {KEY_FILE} 파일을 만들어 키만 적어 주세요.')
    voices = call(key, 'voices?languageCode=he-IL')['voices']
    # 음질이 좋은 순서로 여성·남성 한 명씩 고른다
    rank = lambda v: next((i for i, t in enumerate(('Chirp3-HD', 'Chirp-HD', 'Neural2', 'Wavenet')) if t in v['name']), 9)
    picked = [min((v for v in voices if v['ssmlGender'] == g), key=rank, default=None) for g in ('FEMALE', 'MALE')]
    picked = [v for v in picked if v]
    print('사용 가능한 음성:', ', '.join(v['name'] for v in voices))
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (shown, spoken, hg) in enumerate(WORDS):
        cells = []
        for v in picked:
            audio = call(key, 'text:synthesize', {'input': {'text': spoken}, 'voice': {'languageCode': 'he-IL', 'name': v['name']},
                                                  'audioConfig': {'audioEncoding': 'MP3'}})['audioContent']
            name = f"{i:02d}-{re.sub(r'[^A-Za-z0-9-]', '', v['name'])}.mp3"
            (OUT / name).write_bytes(base64.b64decode(audio))
            cells.append(f'<td><audio controls preload="none" src="{name}"></audio></td>')
        rows.append(f'<tr><td class="he">{shown}</td><td>{hg}</td>{"".join(cells)}</tr>')
        print(f'{i + 1}/{len(WORDS)} {hg}')
    head = ''.join(f"<th>{v['name']} ({v['ssmlGender']})</th>" for v in picked)
    (OUT / 'index.html').write_text(
        '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>음성 샘플</title>'
        '<style>body{font:15px/1.5 sans-serif;margin:16px}table{border-collapse:collapse}td,th{padding:6px 10px;border-bottom:1px solid #ccc;text-align:left}'
        '.he{font-size:26px;direction:rtl}audio{height:36px;max-width:220px}</style><h1>음성 샘플 20단어</h1>'
        f'<table><tr><th>단어</th><th>앱 발음</th>{head}</tr>{"".join(rows)}</table></html>', encoding='utf-8')
    print('완료:', OUT / 'index.html')


main()
