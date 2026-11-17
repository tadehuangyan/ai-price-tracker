import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: true, // 监听所有网卡，支持局域网访问
    port: 5173,
    // 内网穿透/自定义域名访问时跳过 Host 白名单校验（Vite 默认对陌生 Host 返回 403）
    allowedHosts: true,
    // API 与上传文件走开发服务器代理，页面与接口同源，穿透/局域网均可访问
    proxy: {
      '/api': { target: 'http://localhost:8001', changeOrigin: true },
      '/uploads': { target: 'http://localhost:8001', changeOrigin: true },
    },
  },
})
