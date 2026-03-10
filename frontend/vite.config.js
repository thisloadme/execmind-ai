import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: [
      '8175-2001-448a-40b0-e55f-b222-5125-b9ef-173d.ngrok-free.app'
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '/ready': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
})
