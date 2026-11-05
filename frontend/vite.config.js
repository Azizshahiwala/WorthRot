import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/analyze": "http://127.0.0.1:5000",
      "/analyze-media": "http://127.0.0.1:5000",
      "/compare": "http://127.0.0.1:5000",
      "/health": "http://127.0.0.1:5000",
    },
  },
  test: {
    environment: "jsdom",
    restoreMocks: true,
  },
});
