import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true
  },
  define: {
    // Make environment variables available to the app
    __BACKEND_URL__: JSON.stringify(process.env.BACKEND_URL || 'http://localhost:8001'),
    __PRODUCTION_BACKEND_URL__: JSON.stringify(process.env.PRODUCTION_BACKEND_URL || ''),
    __ENVIRONMENT__: JSON.stringify(process.env.ENVIRONMENT || 'development')
  }
})
