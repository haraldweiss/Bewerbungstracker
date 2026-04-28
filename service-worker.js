/**
 * Service Worker for Bewerbungs-Tracker
 * Enables offline support, caching, and background sync
 *
 * Strategy:
 *  - Static assets (HTML/CSS/JS/images/manifest): cache-first with network fallback
 *  - API requests (/api/*): network-only, NEVER cached (prevents stale auth / data poisoning)
 *  - Service worker itself: never cached (ensures updates propagate)
 */

// Bump bei jedem Frontend-Release das index.html / static assets ändert,
// sonst bleibt die alte Version aus dem SW-Cache hängen.
const CACHE_NAME = 'bewerbungs-tracker-v4';
const OFFLINE_URL = '/';

// Static assets to pre-cache on install. Explicitly excludes service-worker.js
// so updates always come from the network.
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json'
];

// Extensions considered cacheable static assets
const STATIC_ASSET_EXTENSIONS = [
  '.html', '.css', '.js', '.mjs',
  '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
  '.woff', '.woff2', '.ttf', '.otf', '.eot',
  '.webmanifest', '.json'
];

function isApiRequest(url) {
  return url.includes('/api/');
}

function isServiceWorkerRequest(url) {
  return url.endsWith('/service-worker.js') || url.endsWith('/sw.js');
}

function isStaticAsset(url) {
  // Treat root navigations as static HTML
  try {
    const u = new URL(url);
    if (u.pathname === '/' || u.pathname === '/index.html') return true;
    const lower = u.pathname.toLowerCase();
    return STATIC_ASSET_EXTENSIONS.some((ext) => lower.endsWith(ext));
  } catch (e) {
    return false;
  }
}

// ═══════════════════════════════════════════════════════
// INSTALL EVENT - Cache essential assets
// ═══════════════════════════════════════════════════════
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing', CACHE_NAME);
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[Service Worker] Caching essential assets');
      return cache.addAll(ASSETS_TO_CACHE).catch((err) => {
        console.warn('[Service Worker] Cache error (continuing):', err);
      });
    })
  );
  self.skipWaiting();
});

// ═══════════════════════════════════════════════════════
// ACTIVATE EVENT - Clean up old caches
// ═══════════════════════════════════════════════════════
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating', CACHE_NAME);
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// ═══════════════════════════════════════════════════════
// FETCH EVENT
// ═══════════════════════════════════════════════════════
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const { method, url } = request;

  // Only handle GET requests
  if (method !== 'GET') {
    return;
  }

  // Skip non-http(s) requests (chrome-extension://, data:, etc.)
  if (!url.startsWith('http')) {
    return;
  }

  // NEVER cache the service worker itself – updates must come from network
  if (isServiceWorkerRequest(url)) {
    event.respondWith(fetch(request));
    return;
  }

  // API requests: network-only, NEVER cached.
  // On offline/failure, return a JSON fallback with HTTP 503 so callers know
  // this is NOT real data. The fallback is constructed on the fly – it never
  // lands in any Cache Storage, so it cannot poison subsequent requests.
  if (isApiRequest(url)) {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(
          JSON.stringify({
            status: 'offline',
            message: 'You are offline. Changes will sync when online.'
          }),
          {
            status: 503,
            statusText: 'Service Unavailable (offline)',
            headers: {
              'Content-Type': 'application/json',
              'Cache-Control': 'no-store'
            }
          }
        );
      })
    );
    return;
  }

  // Static assets: cache-first, network fallback.
  // Only cache responses that look like static assets (by extension / root path).
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request)
        .then((response) => {
          if (response.ok && isStaticAsset(url) && !isServiceWorkerRequest(url)) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((c) => c.put(request, clone));
          }
          return response;
        })
        .catch(() => {
          // Offline fallback: serve the cached shell for navigations
          return caches.match(OFFLINE_URL);
        });
    })
  );
});

// ═══════════════════════════════════════════════════════
// MESSAGE HANDLING - Communication with main thread
// ═══════════════════════════════════════════════════════
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.delete(CACHE_NAME).then(() => {
      if (event.ports && event.ports[0]) {
        event.ports[0].postMessage({ success: true });
      }
    });
  }
});

// ═══════════════════════════════════════════════════════
// BACKGROUND SYNC - placeholder (no API caching happens here anymore)
// ═══════════════════════════════════════════════════════
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-applications') {
    // API responses are no longer cached; real sync is handled by the app
    // itself using queued mutations in the main thread.
    console.log('[Service Worker] sync event received (no-op, handled by app):', event.tag);
  }
});

console.log('[Service Worker] Loaded and ready:', CACHE_NAME);
