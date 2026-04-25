import react from "@vitejs/plugin-react-swc";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/** Vite /api → FastAPI. Prefer POE2B_DEV_API_PROXY (set in deploy compose); VITE_ can be overridden by empty .env.mounted files. */
const devApiProxy = (() => {
  for (const key of ["POE2B_DEV_API_PROXY", "VITE_API_PROXY_TARGET"] as const) {
    const v = process.env[key]?.trim();
    if (v) return v;
  }
  // Local `npm run dev` with API on the host; avoid `http://backend` (ENOTFOUND outside compose DNS).
  return "http://127.0.0.1:8000";
})();

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
        target: devApiProxy,
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
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
