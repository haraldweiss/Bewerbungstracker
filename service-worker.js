/**
 * Service Worker for Bewerbungs-Tracker
 * Enables offline support, caching, and background sync
 */

const CACHE_NAME = 'bewerbungs-tracker-v1';
const OFFLINE_URL = '/';

// Files to cache on install
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/manifest.json',
  '/service-worker.js',
  '/style.css'
];

// ═══════════════════════════════════════════════════════
// INSTALL EVENT - Cache essential assets
// ═══════════════════════════════════════════════════════
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
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
  console.log('[Service Worker] Activating...');
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
// FETCH EVENT - Network-first strategy with offline fallback
// ═══════════════════════════════════════════════════════
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const { method, url } = request;

  // Only handle GET requests
  if (method !== 'GET') {
    return;
  }

  // Skip non-http requests
  if (!url.startsWith('http')) {
    return;
  }

  // API requests: Network first, cache fallback
  if (url.includes('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache successful responses
          if (response.ok) {
            const cache = caches.open(CACHE_NAME);
            cache.then((c) => c.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => {
          // Offline: Try cache, then offline response
          return caches.match(request).then((cached) => {
            if (cached) {
              return cached;
            }
            // Return offline placeholder for API calls
            return new Response(
              JSON.stringify({
                status: 'offline',
                message: 'You are offline. Changes will sync when online.'
              }),
              {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
              }
            );
          });
        })
    );
    return;
  }

  // Static assets: Cache first, network fallback
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request)
        .then((response) => {
          // Cache successful responses
          if (response.ok) {
            const cache = caches.open(CACHE_NAME);
            cache.then((c) => c.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => {
          // Offline: Return offline page
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
      event.ports[0].postMessage({ success: true });
    });
  }
});

// ═══════════════════════════════════════════════════════
// BACKGROUND SYNC - Sync data when online
// ═══════════════════════════════════════════════════════
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-applications') {
    event.waitUntil(syncApplications());
  }
});

async function syncApplications() {
  try {
    const cache = await caches.open(CACHE_NAME);
    const requests = await cache.keys();

    for (const request of requests) {
      if (request.url.includes('/api/applications')) {
        try {
          const response = await fetch(request.clone());
          if (response.ok) {
            await cache.put(request, response.clone());
          }
        } catch (err) {
          console.log('[Service Worker] Sync error:', err);
        }
      }
    }
  } catch (err) {
    console.error('[Service Worker] Background sync failed:', err);
  }
}

console.log('[Service Worker] Loaded and ready');
