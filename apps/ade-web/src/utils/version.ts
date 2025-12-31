const envVersion = typeof import.meta.env.VITE_APP_VERSION === "string" ? import.meta.env.VITE_APP_VERSION : undefined;
const buildVersion = typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : undefined;
const normalized = (envVersion ?? buildVersion ?? "").trim();

export const ADE_WEB_VERSION = normalized || "unknown";
