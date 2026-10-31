const CACHE_NAME = 'milestone-cache-v6';
const APP_SHELL = [
  './',
  'manifest.json',
  'icons/icon-180.png',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/icon.svg'
];

// What the last page navigation was served from, so the page can tell which copy of the app it is running (the page asks with {type:'nav-stamp'}). Kept in memory and in the
// cache (the worker is stopped and restarted often). 'cache' means the saved copy was used because the server could not be reached: that page may be out of date.
const META_KEY = 'milestone-last-nav';
let lastNav = null;
const stampOf = (h) => h.get('etag') || h.get('last-modified') || h.get('content-length') || '';
function remember(res, source) {
  lastNav = { stamp: stampOf(res.headers), source };
  caches.open(CACHE_NAME).then((c) => c.put(META_KEY, new Response(JSON.stringify(lastNav)))).catch(() => {});
}

self.addEventListener('message', (event) => {
  if (!event.data || event.data.type !== 'nav-stamp' || !event.source) return;
  const reply = (info) => event.source.postMessage({ type: 'nav-stamp', stamp: info.stamp || '', source: info.source || '' });
  if (lastNav) { reply(lastNav); return; }
  event.waitUntil(
    caches.open(CACHE_NAME).then((c) => c.match(META_KEY)).then((r) => (r ? r.json() : {})).catch(() => ({})).then(reply)
  );
});

self.addEventListener('install', (event) => {
  // cache.addAll() is all-or-nothing — cache each entry independently so one
  // failed request (a CDN hiccup) doesn't disable offline support entirely.
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => Promise.all(APP_SHELL.map((url) =>
        cache.add(url).catch((err) => console.warn('milestone sw: failed to precache', url, err))
      )))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  if (req.mode === 'navigate') {
    event.respondWith(
      // no-cache: always revalidate with the server — the plain dev server sends no cache headers, so Chrome's HTTP cache would otherwise keep handing back an old page after an edit.
      fetch(req.url, { cache: 'no-cache' })
        .then((res) => {
          // An error page (404/500 from a dead or misconfigured server) must not replace the good saved copy or count as the running version.
          if (!res.ok) throw new Error('bad navigation response ' + res.status);
          remember(res, 'network');
          const copy = res.clone();   // clone before returning: cloning later races the page reading the body
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('./')).then((cached) => {
          if (cached) remember(cached, 'cache');
          return cached;
        }))
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req)
        .then((res) => {
          if (res.ok) caches.open(CACHE_NAME).then((cache) => cache.put(req, res.clone()));   // an error page must not replace the good saved copy
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
