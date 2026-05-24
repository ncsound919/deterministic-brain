
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/engine': { target: 'http://localhost:8100', changeOrigin: true },
      '/health': { target: 'http://localhost:8100', changeOrigin: true },
      '/api': { target: 'http://localhost:8000', changeOrigin: true, rewrite: p => p.replace(/^\/api/, '') },
    }
  }
})
