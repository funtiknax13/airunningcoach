import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Локально: localhost:8000, в Docker dev: backend:8000
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  // altcha-widget — веб-компонент (custom element), не Vue-компонент
  plugins: [vue({
    template: { compilerOptions: { isCustomElement: (tag) => tag.startsWith('altcha-') } },
  })],
  // Меняется на каждой сборке — используется как ключ версии для localStorage-кеша
  // стора (utils/cache.ts), чтобы новый деплой автоматически сбрасывал старый кеш.
  // Ключ версии Service Worker'а (public/sw.js → dist/sw.js) подставляется отдельным
  // шагом ПОСЛЕ vite build — см. package.json ("build") и scripts/inject-sw-version.mjs
  // (пытался сделать это Vite-плагином через buildStart/closeBundle — гонялся с
  // копированием public/ в dist в непредсказуемом порядке, ненадёжно).
  define: {
    __BUILD_ID__: JSON.stringify(Date.now().toString()),
  },
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api':      API_TARGET,
      '/sqladmin': API_TARGET,   // sqladmin переехал сюда; /admin теперь SPA-роут
      '/health':   API_TARGET,
      '/docs':     API_TARGET,
      '/images':   API_TARGET,
    },
  },
  build: {
    outDir: '../frontend-v2-dist',
    emptyOutDir: true,
  },
})
