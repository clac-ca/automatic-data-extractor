import { defineConfig } from "vitest/config.js";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: true,
    coverage: {
      reporter: ["text", "html"],
      reportsDirectory: "./coverage",
    },
  },
});
