/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // R-11 (risk register): this repo lives on a OneDrive-synced /mnt/c
    // mount under WSL2, which does not deliver native filesystem change
    // events reliably (9p, not inotify) — Vite's default watcher silently
    // serves stale transforms with no error instead of picking up edits.
    // Polling is slower but correct; verified live (a source edit was
    // NOT picked up without this, reproducing a real React duplicate-key
    // warning from stale code during Sprint 10's E2E walkthrough).
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    globals: true,
  },
})
