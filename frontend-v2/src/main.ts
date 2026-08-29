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
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
