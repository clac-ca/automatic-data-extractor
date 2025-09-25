import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  preview: {
    port: 4173,
  },
  build: {
    sourcemap: true
  },
  resolve: {
    alias: {
      "@app": "/src/app",
      "@api": "/src/api",
      "@components": "/src/components",
      "@pages": "/src/pages",
      "@styles": "/src/styles"
    }
  }
});
