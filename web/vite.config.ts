import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the API runs on port 8010 (uv run uvicorn firecal.api:app --reload --port 8010).
// Set API_URL to point the dev server at an API somewhere else.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': process.env.API_URL ?? 'http://127.0.0.1:8010' },
  },
})
