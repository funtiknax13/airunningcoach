import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/auth':        'http://localhost:8000',
      '/activities':  'http://localhost:8000',
      '/goals':       'http://localhost:8000',
      '/training':    'http://localhost:8000',
      '/chat':        'http://localhost:8000',
      '/ai-insights': 'http://localhost:8000',
      '/images':      'http://localhost:8000',
    },
  },
  build: {
    outDir: '../frontend-v2-dist',
    emptyOutDir: true,
  },
})
