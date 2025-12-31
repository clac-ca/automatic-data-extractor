import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";
import react from "@vitejs/plugin-react";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));
const resolveSrc = (relativePath: string) => path.resolve(projectRoot, "src", relativePath);
const packageJsonPath = fileURLToPath(new URL("./package.json", import.meta.url));
const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8")) as { version?: string };
const appVersion = packageJson.version ?? "unknown";

const parsedFrontendPort = Number.parseInt(process.env.DEV_FRONTEND_PORT ?? "8000", 10);
const frontendPort = Number.isNaN(parsedFrontendPort) ? 8000 : parsedFrontendPort;
const parsedBackendPort = Number.parseInt(process.env.DEV_BACKEND_PORT ?? "8001", 10);
const backendPort = Number.isNaN(parsedBackendPort) ? 8001 : parsedBackendPort;

if (backendPort === frontendPort) {
  throw new Error(
    `DEV_BACKEND_PORT (${backendPort}) must not match DEV_FRONTEND_PORT (${frontendPort}); otherwise the /api proxy will loop.`,
  );
}

export default defineConfig({
  plugins: [tailwindcss(), react(), tsconfigPaths()],
  resolve: {
    alias: {
      "@pages": resolveSrc("pages"),
      "@components": resolveSrc("components"),
      "@api": resolveSrc("api"),
      "@navigation": resolveSrc("navigation"),
      "@hooks": resolveSrc("hooks"),
      "@utils": resolveSrc("utils"),
      "@schema": resolveSrc("types"),
      "@schema/generated": resolveSrc("types/generated"),
      "@test": resolveSrc("test"),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    port: frontendPort,
    strictPort: true,
    host: process.env.DEV_FRONTEND_HOST ?? "0.0.0.0",
    proxy: {
      "/api": {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
