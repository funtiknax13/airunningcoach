// Плейсхолдер подставляется в dist/sw.js отдельным шагом после vite build — см.
// package.json ("build") и scripts/inject-sw-version.mjs. Раньше здесь была
// статичная строка, никогда не менявшаяся между деплоями, из-за чего activate()
// ничего не чистил и старый CacheStorage жил вечно.
const CACHE = 'runcoach-__SW_CACHE_VERSION__'
const STATIC = ['/', '/dashboard', '/manifest.json', '/logo.png', '/favicon.ico']

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url)

  // API-запросы — только сеть, без кеша
  if (url.pathname.startsWith('/api/')) return

  // Навигации (сам SPA-документ) — только сеть, кеш лишь как офлайн-фоллбэк.
  // JS/CSS с хэшем в имени безопасно отдавать из кеша (URL иммутабелен — при
  // новой сборке будет уже другой файл), а вот HTML — нет: cache-first здесь
  // означало, что вернувшийся после деплоя пользователь мгновенно получал
  // старую страницу со ссылками на уже удалённые хэшированные файлы (404).
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request).then(c => c || caches.match('/')))
    )
    return
  }

  e.respondWith(
    caches.match(e.request).then(cached => {
      const network = fetch(e.request).then(res => {
        // clone() нужно вызвать СРАЗУ, пока тело ответа никто не начал читать —
        // если отложить его до открытия кеша (асинхронно), res может успеть
        // уйти дальше и начать читаться раньше, чем сюда дойдёт очередь.
        if (res.ok && e.request.method === 'GET') {
          const resClone = res.clone()
          caches.open(CACHE).then(c => c.put(e.request, resClone))
        }
        return res
      })
      return cached || network
    })
  )
})

self.addEventListener('push', e => {
  let data = { title: 'AI RunningCoach', body: '', url: '/dashboard' }
  if (e.data) {
    try { data = { ...data, ...e.data.json() } } catch (err) { data.body = e.data.text() }
  }
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/logo.png',
      badge: '/logo.png',
      data: { url: data.url || '/dashboard' },
    })
  )
})

self.addEventListener('notificationclick', e => {
  e.notification.close()
  const url = (e.notification.data && e.notification.data.url) || '/dashboard'
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      for (const client of clients) {
        if ('focus' in client) { client.navigate(url); return client.focus() }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })
  )
})
