"""창세기의 모든 히브리어 형태를 Google Cloud TTS로 만들어 docs/audio/에 넣는다. 이미 있는 파일은 건너뛴다.

키는 .secrets/google_tts_key.txt 또는 환경 변수 GOOGLE_TTS_API_KEY에서 읽는다.
사용법: python tts_build.py [개수 제한]
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pron

ROOT = Path(__file__).parent.parent
KEY_FILE = ROOT / '.secrets' / 'google_tts_key.txt'
OUT = ROOT / 'docs' / 'audio'
VOICE = 'he-IL-Chirp3-HD-Achernar'
URL = 'https://texttospeech.googleapis.com/v1/text:synthesize'
key = os.environ.get('GOOGLE_TTS_API_KEY') or KEY_FILE.read_text(encoding='utf-8').strip()


def synth(item):
    name, text = item
    body = json.dumps({'input': {'text': text}, 'voice': {'languageCode': 'he-IL', 'name': VOICE},
                       'audioConfig': {'audioEncoding': 'MP3'}}).encode()
    for attempt in range(6):
        req = urllib.request.Request(URL, data=body, headers={'X-Goog-Api-Key': key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                (OUT / f'{name}.mp3').write_bytes(base64.b64decode(json.load(r)['audioContent']))
            return None
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503):
                return f'{name} {text} 오류 {e.code}'
        except OSError:
            pass
        time.sleep(2 ** attempt)
    return f'{name} {text} 재시도 초과'


def main():
    forms = {}
    for part in sorted((ROOT / 'build' / 'parts').glob('gen-*.json')):
        for c in json.loads(part.read_text(encoding='utf-8'))['chapters']:
            for v in c['verses']:
                for w in v['w']:
                    forms[w['a']] = pron.spoken(w['t'])
    OUT.mkdir(parents=True, exist_ok=True)
    todo = [(n, t) for n, t in forms.items() if not (OUT / f'{n}.mp3').exists()]
    if len(sys.argv) > 1:
        todo = todo[:int(sys.argv[1])]
    print(f'전체 {len(forms)}개, 만들 것 {len(todo)}개, 글자 수 {sum(len(t) for _, t in todo)}', flush=True)
    with ThreadPoolExecutor(8) as pool:
        errors = [e for i, e in enumerate(pool.map(synth, todo)) if e or (i + 1) % 500 == 0 and print(i + 1, flush=True)]
    print('실패', len(errors), *errors[:20], sep='\n')
    print('완료 파일 수', len(list(OUT.glob('*.mp3'))))
    sys.exit(1 if errors else 0)


main()
