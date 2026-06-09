import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// Локально: localhost:8000, в Docker dev: backend:8000
const API_TARGET = process.env.VITE_API_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/api':    API_TARGET,
      '/admin':  API_TARGET,
      '/health': API_TARGET,
      '/docs':   API_TARGET,
      '/images': API_TARGET,
    },
  },
  build: {
    outDir: '../frontend-v2-dist',
    emptyOutDir: true,
  },
})
