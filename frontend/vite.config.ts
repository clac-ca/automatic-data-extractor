import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { reactRouter } from "@react-router/dev/vite";

// Ensure singletons for React and React Router across the app and dependencies.
// Without this, duplicate copies can lead to mismatched contexts where the URL
// changes but consumers (NavLink/useMatches/Outlet) don't see updates.
export default defineConfig({
  plugins: [reactRouter(), react()],
  resolve: {
    dedupe: ["react", "react-dom", "react-router", "react-router-dom"],
  },
  optimizeDeps: {
    // Pre-bundle these to avoid multiple copies sneaking in during dev.
    include: ["react", "react-dom", "react-router", "react-router-dom"],
  },
});
