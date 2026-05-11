import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
	server: {
		// Docker内からのアクセス許可
		host: '0.0.0.0',
		port: 80,
		allowedHosts: ['localhost', '127.0.0.1'],
		// APIプロキシ設定 (Nginxの代わり)
		proxy: {
			'/api': {
				target: 'http://backend:3000',
				changeOrigin: true,
			},
		},
	},
})
