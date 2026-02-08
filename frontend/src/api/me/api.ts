import { client } from "@/api/client";
import type { MeProfile } from "@/types";

export interface MeRequestOptions {
  readonly signal?: AbortSignal;
}

export interface UpdateMyProfileRequest {
  readonly display_name?: string | null;
}

export async function fetchMyProfile(options: MeRequestOptions = {}): Promise<MeProfile> {
  const { data } = await client.GET("/api/v1/me", {
    signal: options.signal,
  });

  if (!data) {
    throw new Error("Expected profile payload.");
  }

  return data;
}

export async function updateMyProfile(payload: UpdateMyProfileRequest): Promise<MeProfile> {
  const { data } = await client.PATCH("/api/v1/me", {
    body: payload,
  });

  if (!data) {
    throw new Error("Expected updated profile payload.");
  }

  return data;
}
