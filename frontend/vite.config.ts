import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Traefik forwards the browser Host header; Vite must allow it (DNS rebinding guard).
    allowedHosts: [
      "localhost",
      "app.localhost",
      "app.dev.hideoutbutler.com",
      ...(process.env.VITE_ALLOWED_HOSTS?.split(/[\s,]+/).filter(Boolean) ?? []),
    ],
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET ?? "http://backend:8000",
        changeOrigin: false,
      },
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
