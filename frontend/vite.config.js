import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies API calls to the FastAPI backend on :8000 so the
// browser treats them as same-origin (cookies + no CORS friction in dev).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Only API calls are proxied to the backend. Admin & client UI routes
      // (/admin/*, /v/*) fall through to the SPA so a hard refresh works.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
