const CACHE_NAME = 'milestone-cache-v5';
const APP_SHELL = [
  'milestone.html',
  'manifest.json',
  'icons/icon-180.png',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/icon.svg'
];

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
      fetch(req)
        .then((res) => {
          if (res.ok) caches.open(CACHE_NAME).then((cache) => cache.put(req, res.clone()));   // an error page must not replace the good saved copy
          return res;
        })
        .catch(() => caches.match(req).then((cached) => cached || caches.match('milestone.html')))
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
