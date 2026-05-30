import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    allowedHosts: ['eventfinder.thunderbee.uk'],
    host: true,
    proxy: {
      '/auth': { target: 'http://backend:8000', changeOrigin: true },
      '/events': { target: 'http://backend:8000', changeOrigin: true },
    },
  },
})
