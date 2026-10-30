// 앱 화면과 본문을 저장해 두고 오프라인에서도 연다. 값은 build_app.py가 채운다.
const CACHE = 'ob-7a80b21512';
const FILES = ["./", "icons/icon-192.png", "icons/icon-512.png", "index.html", "manifest.webmanifest", "parts/gen-01-11.json", "parts/gen-12-25.json", "parts/gen-26-50.json", "parts/jhn-01.json"];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(caches.match(e.request, { ignoreSearch: true }).then(hit => hit || fetch(e.request)));
});
