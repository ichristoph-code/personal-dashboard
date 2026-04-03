// sw.js -- Service Worker for Dashboard PWA
var CACHE_NAME = 'dashboard-v4';

self.addEventListener('install', function(event) {
    // Pre-cache the core shell
    event.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            return cache.addAll([
                '/manifest.json',
                '/icon-192.png',
                '/icon-512.png'
            ]);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    // Clean old caches
    event.waitUntil(
        caches.keys().then(function(names) {
            return Promise.all(
                names.filter(function(n) { return n !== CACHE_NAME; })
                    .map(function(n) { return caches.delete(n); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function(event) {
    var url = new URL(event.request.url);

    // Network-first for dashboard.html and API endpoints
    if (url.pathname === '/dashboard.html' || url.pathname === '/' ||
        url.pathname === '/refresh' || url.pathname === '/claude-query' ||
        url.pathname === '/manage-feeds') {
        event.respondWith(
            fetch(event.request).then(function(response) {
                // Cache successful HTML responses for offline fallback
                if (url.pathname === '/dashboard.html' || url.pathname === '/') {
                    var clone = response.clone();
                    caches.open(CACHE_NAME).then(function(cache) {
                        cache.put(event.request, clone);
                    });
                }
                return response;
            }).catch(function() {
                return caches.match(event.request).then(function(cached) {
                    return cached || offlineResponse();
                });
            })
        );
        return;
    }

    // Cache-first for static assets (CSS, JS, images)
    // These have ?v=mtime cache busters, so new builds auto-fetch new URLs
    if (url.pathname.startsWith('/templates/') ||
        url.pathname.match(/\.(png|jpg|svg|ico|json)$/)) {
        event.respondWith(
            caches.match(event.request).then(function(cached) {
                if (cached) return cached;
                return fetch(event.request).then(function(response) {
                    var clone = response.clone();
                    caches.open(CACHE_NAME).then(function(cache) {
                        cache.put(event.request, clone);
                    });
                    return response;
                });
            })
        );
        return;
    }

    // Stale-while-revalidate for CDN resources (Chart.js)
    if (url.hostname === 'cdn.jsdelivr.net') {
        event.respondWith(
            caches.match(event.request).then(function(cached) {
                var fetchPromise = fetch(event.request).then(function(response) {
                    var clone = response.clone();
                    caches.open(CACHE_NAME).then(function(c) {
                        c.put(event.request, clone);
                    });
                    return response;
                });
                return cached || fetchPromise;
            })
        );
        return;
    }

    // Default: network with cache fallback
    event.respondWith(
        fetch(event.request).catch(function() {
            return caches.match(event.request);
        })
    );
});

function offlineResponse() {
    var html = '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        + '<meta name="viewport" content="width=device-width,initial-scale=1">'
        + '<title>Offline</title>'
        + '<style>body{font-family:-apple-system,sans-serif;display:flex;align-items:center;'
        + 'justify-content:center;min-height:100vh;background:#1a1a2e;color:#fff;text-align:center;margin:0}'
        + 'h1{font-size:1.5em;margin-bottom:8px}p{color:rgba(255,255,255,0.6);font-size:0.9em}'
        + 'button{margin-top:20px;padding:12px 28px;border:none;border-radius:8px;background:#667eea;'
        + 'color:#fff;font-size:1em;cursor:pointer;min-height:44px}</style></head>'
        + '<body><div><h1>You\'re Offline</h1>'
        + '<p>Your dashboard will return when you reconnect.</p>'
        + '<button onclick="location.reload()">Try Again</button></div></body></html>';
    return new Response(html, {
        headers: { 'Content-Type': 'text/html' }
    });
}
