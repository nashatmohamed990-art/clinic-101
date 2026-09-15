// Minimal service worker: makes the site installable as an app and caches
// only static assets (icons, fonts) for a faster/offline-tolerant shell.
// It deliberately does NOT cache HTML pages or API responses (/slots, /book,
// appointment lists, etc.) — this is a clinic booking system, and showing
// stale appointment data offline would be actively harmful, not helpful.

const CACHE_NAME = 'alfaidy-static-v1';
const STATIC_ASSETS = [
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/fonts/Arabic-Regular.ttf',
  '/static/fonts/Arabic-Bold.ttf',
  '/static/images/logo.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Only ever serve cached responses for our known static assets.
  // Everything else (pages, /slots, /book, login, etc.) always goes to the
  // network so the clinic never sees outdated appointment data.
  if (event.request.method === 'GET' && STATIC_ASSETS.some((p) => url.pathname === p)) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
