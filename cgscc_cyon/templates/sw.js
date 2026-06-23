const CACHE_NAME = 'cyon-harvest-v1';
const urlsToCache = [
  '/',
  '/static/css/index.css',
  '/static/images/brand/church-seal.png',
  '/static/images/brand/cyon-logo.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
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

// Push Notification Event Listener
self.addEventListener('push', function(event) {
    if (event.data) {
        const data = event.data.json();
        const title = data.title || 'CYON Harvest Update';
        const options = {
            body: data.body || 'You have a new update.',
            icon: '/static/images/brand/church-seal.png',
            badge: '/static/images/brand/church-seal.png',
            vibrate: [200, 100, 200]
        };
        
        event.waitUntil(
            self.registration.showNotification(title, options)
        );
    }
});

// Click event for notification
self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/')
    );
});
