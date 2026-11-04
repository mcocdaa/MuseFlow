import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendOrigin = env.VITE_BACKEND_ORIGIN || process.env.VITE_BACKEND_ORIGIN || 'http://127.0.0.1:8765'

  return {
    plugins: [
      vue(),
      tailwindcss(),
    ],
    server: {
      port: Number(env.VITE_DEV_PORT || 5173),
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: backendOrigin,
          changeOrigin: true,
        },
      },
    },
  }
})

