import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dev: proxies /api to uvicorn on :8000, or to a running compose stack with
// OPENWATCH_API=https://localhost:39443 npm run dev
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: process.env.OPENWATCH_API ?? "http://localhost:8000", secure: false, changeOrigin: true } } },
});
