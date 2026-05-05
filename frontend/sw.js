// Maintenance-Eye Service Worker
// Provides offline support and PWA functionality

const CACHE_NAME = 'maintenance-eye-v15';
const ASSETS = [
    '/',
    '/index.html',
    '/style.css',
    '/command-center.css',
    '/app.js',
    '/command-center.js',
    '/manifest.json',
    '/icons/icon-192.png',
    '/icons/icon-512.png',
];

// Install
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys
                .filter(key => key !== CACHE_NAME)
                .map(key => caches.delete(key))
            )
        ).then(() => self.clients.claim())
    );
});

// Fetch — Network first, cache fallback
self.addEventListener('fetch', (event) => {
    // Skip non-GET and WebSocket requests
    if (event.request.method !== 'GET' || event.request.url.includes('/ws/')) {
        return;
    }

    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(response => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
