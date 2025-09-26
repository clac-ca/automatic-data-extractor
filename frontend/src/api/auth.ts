import type { Session, SessionUser } from "@app/providers/SessionProvider";

import { ApiClient } from "@api/client";

interface TokenResponse {
  readonly access_token: string;
  readonly token_type?: string;
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
  const token = await client.post<TokenResponse>("/auth/token", {
    json: {
      username: credentials.email,
      password: credentials.password
    }
  });

  const profile = await client.get<UserProfileResponse>("/auth/me", {
    headers: {
      Authorization: `Bearer ${token.access_token}`
    }
  });

  const user: SessionUser = {
    id: profile.user_id,
    email: profile.email,
    role: profile.role,
    isActive: profile.is_active,
    displayName: profile.email.split("@")[0] ?? profile.email
  };

  return {
    accessToken: token.access_token,
    user
  };
}
