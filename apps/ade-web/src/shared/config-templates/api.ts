import { client } from "@shared/api/client";

import type { ConfigTemplate } from "./types";

export async function listConfigTemplates(signal?: AbortSignal): Promise<ConfigTemplate[]> {
  const { data } = await client.GET("/api/v1/config-templates", { signal });
  if (!data) {
    throw new Error("Expected config template list payload.");
  }
  return data as ConfigTemplate[];
}
