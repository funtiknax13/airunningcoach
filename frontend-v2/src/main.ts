import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { i18n } from './i18n'
import router from './router'
import App from './App.vue'
import 'altcha'   // регистрирует веб-компонент <altcha-widget> (капча)
import './style.css'
import { captureUtmFromUrl } from './utils/utm'

captureUtmFromUrl()

const app = createApp(App)
app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')

if ('serviceWorker' in navigator) {
  // Новый SW берёт управление сразу (skipWaiting/clients.claim в sw.js) — без
  // этого уже открытая вкладка продолжает жить со старым JS в памяти под новым
  // воркером, ничего пользователю не сигналя. refreshing-флаг — чтобы не
  // зациклиться, если controllerchange прилетит больше одного раза подряд.
  let refreshing = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return
    refreshing = true
    window.location.reload()
  })
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
