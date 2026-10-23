import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from 'tailwindcss'
import autoprefixer from 'autoprefixer'
import portalTheme from './tailwind.config.js'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Import the theme as a Vite dependency so config edits restart the dev
  // server. Passing the object also avoids Tailwind's cached file loader.
  css: { postcss: { plugins: [tailwindcss(portalTheme), autoprefixer()] } },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
