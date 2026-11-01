import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev: proxies /ui to the backend for frontend (apps/bff) on :8001, or to a running compose stack with
// OPENWATCH_UI=https://localhost:39443 npm run dev
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: { port: 5173, proxy: { "/ui": { target: process.env.OPENWATCH_UI ?? "http://localhost:8001", secure: false, changeOrigin: true } } },
  // production: no source maps, no console/debugger, vendor code in its own long-cached chunks
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 1100, // maplibre-gl alone is ~1 MB (284 kB gzipped), cached separately
    target: "es2022",
    rollupOptions: { output: { manualChunks: { maplibre: ["maplibre-gl"], react: ["react", "react-dom"] } } },
  },
  esbuild: mode === "production" ? { drop: ["console", "debugger"] } : undefined,
}));
