import type { Config } from "@react-router/dev/config";

export default {
  appDirectory: "src/app",
  // Run in SPA mode; data loads use clientLoader/clientAction
  ssr: false,
} satisfies Config;
