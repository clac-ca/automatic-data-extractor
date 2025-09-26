import type { Session, SessionUser } from "@app/providers/SessionProvider";

import { ApiClient } from "@api/client";

interface SessionEnvelopeResponse {
  readonly user: UserProfileResponse;
  readonly expires_at: string;
  readonly refresh_expires_at: string;
}

interface UserProfileResponse {
  readonly user_id: string;
  readonly email: string;
  readonly role: string;
  readonly is_active: boolean;
}

export interface SignInCredentials {
  readonly email: string;
  readonly password: string;
}

export async function signIn(
  client: ApiClient,
  credentials: SignInCredentials
): Promise<Session> {
  const session = await client.post<SessionEnvelopeResponse>("/auth/login", {
    json: credentials
  });

  const user = mapProfile(session.user);

  return {
    user,
    expiresAt: session.expires_at,
    refreshExpiresAt: session.refresh_expires_at
  };
}

export async function signOut(client: ApiClient): Promise<void> {
  await client.post("/auth/logout");
}

function mapProfile(profile: UserProfileResponse): SessionUser {
  return {
    id: profile.user_id,
    email: profile.email,
    role: profile.role,
    isActive: profile.is_active,
    displayName: profile.email.split("@")[0] ?? profile.email
  };
}
