const CACHE_NAME = 'cyon-harvest-v2';
const urlsToCache = [
  '/',
  '/static/images/brand/cyon-logo.png',
  '/static/images/brand/church-seal.png'
];

self.addEventListener('install', event => {
  // Don't wait for old tabs to close before activating this version.
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    Promise.all([
      // Drop any caches from older service worker versions.
      caches.keys().then(cacheNames =>
        Promise.all(
          cacheNames
            .filter(name => name !== CACHE_NAME)
            .map(name => caches.delete(name))
        )
      ),
      // Take control of any already-open tabs immediately.
      self.clients.claim()
    ])
  );
});


self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});

self.addEventListener('push', event => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'CYON Harvest Update', body: event.data.text() };
    }
  }

  const title = data.title || 'CYON Harvest Update';
  const options = {
    body: data.body || 'No details provided.',
    icon: data.icon || '/static/images/brand/cyon-logo.png',
    badge: '/static/images/brand/church-seal.png',
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  let targetUrl = '/';
  if (event.notification.data && event.notification.data.url) {
    targetUrl = event.notification.data.url;
  }
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      // If a window is already open, navigate it to targetUrl and focus
      for (let i = 0; i < windowClients.length; i++) {
        let client = windowClients[i];
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.navigate(targetUrl).then(client => client.focus());
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

