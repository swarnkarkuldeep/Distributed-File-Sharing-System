import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev proxy: run each API locally (see README) and open http://localhost:5173
const target = (port: number) => ({
  target: `http://localhost:${port}`,
  changeOrigin: true,
  rewrite: (path: string) => path.replace(/^\/api\/[^/]+/, ""),
});

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api/uploader2": target(8002),
      "/api/uploader": target(8001),
      "/api/downloader": target(8003),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
  },
});
