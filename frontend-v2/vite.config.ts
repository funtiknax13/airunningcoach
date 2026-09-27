import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import fs from 'fs'
import path from 'path'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Локально: localhost:8000, в Docker dev: backend:8000
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

// Dev-only: как nginx (try_files $uri $uri/ /index.html) — каталоги из public/ (блог, инструменты,
// privacy, en...) открываем по их index.html, а не подставляем SPA. В проде это делает nginx.
function publicDirIndex(): Plugin {
  return {
    name: 'public-dir-index',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url || '').split('?')[0]
        if (url === '/' || url.includes('..') || path.extname(url)) return next()
        const dir = path.join(server.config.publicDir, decodeURIComponent(url))
        const index = path.join(dir, 'index.html')
        if (!fs.existsSync(index)) return next()
        if (!url.endsWith('/')) { res.statusCode = 301; res.setHeader('Location', url + '/'); return res.end() }
        res.setHeader('Content-Type', 'text/html; charset=utf-8')
        res.end(fs.readFileSync(index))
      })
    },
  }
}

export default defineConfig({
  // altcha-widget — веб-компонент (custom element), не Vue-компонент
  plugins: [vue({
    template: { compilerOptions: { isCustomElement: (tag) => tag.startsWith('altcha-') } },
  }), publicDirIndex()],
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
