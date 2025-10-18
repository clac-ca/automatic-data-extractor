import type { Config } from "@react-router/dev/config";

export default {
  appDirectory: "src/app",
  ssr: false,
  routes: async () => {
    const { flatRoutes } = await import("@react-router/fs-routes");
    return flatRoutes();
  },
} satisfies Config;
