export const sessionKeys = {
  all: ["session"] as const,
  detail: () => [...sessionKeys.all, "current"] as const,
};
