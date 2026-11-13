import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built bundle is served by the FastAPI backend (uvicorn) from
// frontend/dist; `npm run dev` proxies API and artifact routes to a locally
// running uvicorn instance so no CORS handling is needed.
export default defineConfig({
  // Relative base so one build works at a domain root (FastAPI) and under a
  // GitHub Pages project path such as /HabitatShift/.
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8096",
      "/files": "http://127.0.0.1:8096",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // MapLibre is the largest dependency; keep it in its own cacheable chunk.
        manualChunks: { maplibre: ["maplibre-gl"] },
      },
    },
  },
});
