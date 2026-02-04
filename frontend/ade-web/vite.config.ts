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

const internalApiRaw = process.env.ADE_INTERNAL_API_URL ?? "http://localhost:8001";
const devPort = 8000;

const normalizeInternalApiUrl = (value: string): string => {
  const trimmed = value.replace(/\/+$/, "");
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error(
      `ADE_INTERNAL_API_URL must be an origin like http://localhost:8001 (got "${value}").`,
    );
  }
  if (parsed.pathname !== "/" && parsed.pathname !== "") {
    throw new Error("ADE_INTERNAL_API_URL must not include a path (no /api).");
  }
  if (parsed.search || parsed.hash) {
    throw new Error("ADE_INTERNAL_API_URL must not include query or fragment.");
  }
  return `${parsed.protocol}//${parsed.host}`;
};

const apiTarget = normalizeInternalApiUrl(internalApiRaw);

export default defineConfig({
  plugins: [tailwindcss(), react(), tsconfigPaths()],
  resolve: {
    alias: {
      "@": resolveSrc(""),
    },
  },
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  server: {
    host: true,
    port: devPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
