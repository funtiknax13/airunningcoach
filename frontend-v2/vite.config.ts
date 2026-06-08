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
      '/api':    'http://localhost:8000',
      '/admin':  'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/docs':   'http://localhost:8000',
      '/images': 'http://localhost:8000',
    },
  },
  build: {
    outDir: '../frontend-v2-dist',
    emptyOutDir: true,
  },
})
