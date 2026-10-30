"""템플릿에 목록을 넣어 게시본(dist), 설치형 사이트(docs), 로컬 미리보기를 만들고, 본문 구간 파일을 복사한다."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
page = (ROOT / 'app' / 'template.html').read_text(encoding='utf-8').replace(
    '__MANIFEST__', (ROOT / 'build' / 'manifest.json').read_text(encoding='utf-8'))
(ROOT / 'dist').mkdir(exist_ok=True)
(ROOT / 'dist' / 'original-bible.html').write_text(page, encoding='utf-8')
shutil.copytree(ROOT / 'build' / 'parts', ROOT / 'dist' / 'parts', dirs_exist_ok=True)
# 게시할 때는 문서 뼈대가 자동으로 붙는다. 로컬 미리보기에만 직접 붙인다.
HEAD = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<style>body{margin:0}[hidden]{display:none!important}</style>')
(ROOT / 'build' / 'preview.html').write_text(HEAD + '</head><body>' + page + '</body></html>', encoding='utf-8')

# ---------- 설치형 사이트 (GitHub Pages가 docs/를 그대로 올린다) ----------
SITE = ROOT / 'docs'
SITE.mkdir(exist_ok=True)
shutil.copytree(ROOT / 'build' / 'parts', SITE / 'parts', dirs_exist_ok=True)
shutil.copytree(ROOT / 'app' / 'icons', SITE / 'icons', dirs_exist_ok=True)
(SITE / '.nojekyll').write_text('', encoding='utf-8')
(SITE / 'manifest.webmanifest').write_text(json.dumps({
    'name': '원어 대조 성경', 'short_name': '원어 성경', 'lang': 'ko', 'start_url': './', 'scope': './', 'display': 'standalone',
    'background_color': '#eef2f3', 'theme_color': '#14557b',
    'icons': [{'src': f'icons/icon-{s}.png', 'sizes': f'{s}x{s}', 'type': 'image/png', 'purpose': 'any maskable'} for s in (192, 512)],
}, ensure_ascii=False, indent=1), encoding='utf-8')
(SITE / 'index.html').write_text(
    HEAD + '<link rel="manifest" href="manifest.webmanifest"><meta name="theme-color" content="#14557b">'
    '<link rel="apple-touch-icon" href="icons/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes">'
    '</head><body>' + page +
    "<script>if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js')</script></body></html>", encoding='utf-8')
files = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob('*')
               if p.is_file() and p.name not in ('sw.js', '.nojekyll') and p.parts[len(SITE.parts)] != 'audio')
version = hashlib.sha1(b''.join((SITE / f).read_bytes() for f in files)).hexdigest()[:10]
# 본문은 처음 열 때 모두 저장해 오프라인에서도 열리게 한다. 내용이 바뀌면 version이 바뀌어 새로 받는다.
(SITE / 'sw.js').write_text((ROOT / 'app' / 'sw.js').read_text(encoding='utf-8')
                            .replace('__VERSION__', version).replace('__FILES__', json.dumps(['./'] + files)), encoding='utf-8')
print(f"{(ROOT / 'dist' / 'original-bible.html').stat().st_size // 1024} KB, 사이트 버전 {version}")
