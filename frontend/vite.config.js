import { defineConfig } from 'vite'
import { resolve } from 'path'
import fs from 'fs'
import react from '@vitejs/plugin-react'

// HTTPS local con mkcert (para WebXR en la Quest sin necesidad de internet).
// Si existen los certificados en ../certs arranca en https; si no, en http normal.
const certDir  = resolve(__dirname, '..', 'certs')
const keyPath  = resolve(certDir, 'dev-key.pem')
const certPath = resolve(certDir, 'dev-cert.pem')
const httpsCfg = fs.existsSync(keyPath) && fs.existsSync(certPath)
  ? { key: fs.readFileSync(keyPath), cert: fs.readFileSync(certPath) }
  : undefined

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),   // panel normal
        xr:   resolve(__dirname, 'xr.html'),       // experiencia VR (Quest 3)
      },
    },
  },
  server: {
    host: true,        // expone en la LAN: la Quest llega por la IP del PC (192.168.1.14)
    port: 5173,
    https: httpsCfg,   // https con mkcert si hay certificados; si no, http
    // Permite abrir la app a través del túnel de Cloudflare (si no, Vite bloquea
    // las peticiones cuyo Host no es localhost → "Blocked request").
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/ws':    { target: 'ws://localhost:8080',   ws: true },
      '/video': { target: 'http://localhost:8080'           },
      '/api':   { target: 'http://localhost:8080'           },
    },
  },
})
