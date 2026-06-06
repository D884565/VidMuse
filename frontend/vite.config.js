import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const opencvApiTarget = env.VITE_OPENCV_API_TARGET || 'http://localhost:8000'
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/opencv-api': {
          target: opencvApiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/opencv-api/, ''),
        },
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        '/uploads': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
