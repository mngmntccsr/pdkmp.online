const CACHE_NAME = "paddockmap-v1";

const APP_SHELL = [
  "./",
  "./index.html",
  "./mappa.html",
  "./contatti.html",
  "./map-common.js",
  "./manifest.json",
  "./coordinates.json"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;

  // Gestiamo solo richieste GET
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);

  // events.json: prima prova sempre la rete,
  // così PaddockMap riceve gli eventi aggiornati.
  if (url.pathname.endsWith("/events.json")) {
    event.respondWith(
      fetch(request)
        .then(response => {
          const responseClone = response.clone();

          caches.open(CACHE_NAME).then(cache => {
            cache.put(request, responseClone);
          });

          return response;
        })
        .catch(() => caches.match(request))
    );

    return;
  }

  // Per le risorse locali:
  // prima cache, poi rete.
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(request)
        .then(cachedResponse => {
          if (cachedResponse) {
            return cachedResponse;
          }

          return fetch(request).then(response => {
            if (!response || response.status !== 200) {
              return response;
            }

            const responseClone = response.clone();

            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, responseClone);
            });

            return response;
          });
        })
    );

    return;
  }

  // Per risorse esterne (Leaflet, Google Analytics ecc.)
  // lasciamo funzionare normalmente la rete.
});
