// 앱 화면과 본문을 저장해 두고 오프라인에서도 연다. 값은 build_app.py가 채운다.
const CACHE = 'ob-__VERSION__';
const FILES = __FILES__;
const AUDIO = 'ob-audio-1';   // 음성은 들은 것부터 저장한다. 앱을 고쳐도 지우지 않는다

// 아이폰 사파리는 음성을 범위 요청으로 받으므로 206으로 잘라 준다
function ranged(req, r) {
  const m = /bytes=(\d+)-(\d*)/.exec(req.headers.get('range') || '');
  if (!m || !r.ok) return r;
  return r.arrayBuffer().then(b => {
    const s = +m[1], end = m[2] ? Math.min(+m[2], b.byteLength - 1) : b.byteLength - 1;
    return new Response(b.slice(s, end + 1), { status: 206, headers: {
      'Content-Type': 'audio/mpeg', 'Accept-Ranges': 'bytes', 'Content-Length': String(end - s + 1), 'Content-Range': `bytes ${s}-${end}/${b.byteLength}` } });
  });
}

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE && k !== AUDIO).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  if (new URL(e.request.url).pathname.includes('/audio/')) {
    e.respondWith(caches.open(AUDIO).then(c => c.match(e.request.url).then(hit => hit || fetch(e.request.url).then(r => {
      if (r.ok) c.put(e.request.url, r.clone());
      return r;
    }))).then(r => ranged(e.request, r)));
    return;
  }
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(hit => hit || fetch(e.request)));
});
