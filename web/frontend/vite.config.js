import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file from root directory
  const env = loadEnv(mode, path.resolve(__dirname, '../..'), '')
  
  return {
    plugins: [react()],
    server: {
      port: parseInt(env.FRONTEND_PORT) || 5173,
      host: true
    },
    define: {
      // Make environment variables available to the app
      __BACKEND_URL__: JSON.stringify(env.BACKEND_URL || 'http://localhost:8000'),
      __PRODUCTION_BACKEND_URL__: JSON.stringify(env.PRODUCTION_BACKEND_URL || ''),
      __ENVIRONMENT__: JSON.stringify(env.ENVIRONMENT || 'development')
    }
  }
})
