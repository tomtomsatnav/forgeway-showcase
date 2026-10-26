/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const api = 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  // CodeMirror and the Markdown renderer make the workspace chunk large by nature; it loads on demand.
  build: { chunkSizeWarningLimit: 650 },
  server: {
    port: 5173,
    proxy: { '/api': api, '/healthz': api, '/readyz': api },
  },
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
