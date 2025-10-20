import type { components } from "@api-types";

type Schemas = components["schemas"];

type Schema<T extends keyof Schemas> = Readonly<Schemas[T]>;

export type SessionUser = Schema<"UserProfile">;

type SessionEnvelopeSchema = Schemas["SessionEnvelope"];

export type SessionEnvelope = Readonly<
  SessionEnvelopeSchema & {
    expires_at: string;
    refresh_expires_at: string;
  }
>;

type ProviderDiscoveryResponse = Schema<"ProviderDiscoveryResponse">;

export type AuthProvider = Schema<"AuthProvider">;

export type SessionResponse = Readonly<
  {
    session: SessionEnvelope | null;
  } & ProviderDiscoveryResponse
>;

type LoginRequest = Schemas["LoginRequest"];

export type LoginPayload = Readonly<
  Omit<LoginRequest, "email"> & {
    email: string;
  }
>;

type SetupRequest = Schemas["SetupRequest"];

export type SetupPayload = Readonly<
  Omit<SetupRequest, "email"> & {
    email: string;
  }
>;

export type SetupStatus = Schema<"SetupStatus">;
