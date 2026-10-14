import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolveApiUrl } from './src/config/api-url'

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  // Build validation happens before bundling, including builds with a custom mode.
  const apiUrl = resolveApiUrl(env.VITE_API_URL, command === 'serve')
  return {
    plugins: [react()],
    define: { 'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl) },
  }
})
