import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2020',
    // Pular o cálculo de tamanho gzip acelera o build no Pi 3
    reportCompressedSize: false,
  },
  server: {
    // Em desenvolvimento, encaminha /api para o FastAPI local
    proxy: { '/api': 'http://localhost:8000' },
  },
});
