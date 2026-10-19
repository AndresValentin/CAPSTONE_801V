import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // El backend solo acepta pedidos desde este origen (FRONTEND_ORIGIN en backend/.env).
  // strictPort hace que Vite falle con un aviso claro si el puerto está ocupado, en vez
  // de usar otro puerto en el que el login fallaría.
  server: { port: 5173, strictPort: true },
})
