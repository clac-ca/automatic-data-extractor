import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createSsoProvider,
  deleteSsoProvider,
  listSsoProviders,
  updateSsoProvider,
  validateSsoProvider,
} from "../sso";
import { client } from "@/api/client";

vi.mock("@/api/client", () => ({
  client: {
    GET: vi.fn(),
    POST: vi.fn(),
    PATCH: vi.fn(),
    DELETE: vi.fn(),
  },
}));

describe("admin sso api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists SSO providers", async () => {
    (client.GET as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [] } });
    await listSsoProviders();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/admin/sso/providers", { signal: undefined });
  });

  it("validates provider configuration", async () => {
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        issuer: "https://issuer.example.com",
        authorizationEndpoint: "https://issuer.example.com/oauth2/v1/authorize",
        tokenEndpoint: "https://issuer.example.com/oauth2/v1/token",
        jwksUri: "https://issuer.example.com/oauth2/v1/keys",
      },
    });

    await validateSsoProvider({
      issuer: "https://issuer.example.com",
      clientId: "demo-client",
      clientSecret: "notsecret-client",
    });

    expect(client.POST).toHaveBeenCalledWith("/api/v1/admin/sso/providers/validate", {
      body: {
        issuer: "https://issuer.example.com",
        clientId: "demo-client",
        clientSecret: "notsecret-client",
      },
    });
  });

  it("creates provider", async () => {
    (client.POST as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        id: "okta",
      },
    });

    await createSsoProvider({
      id: "okta",
      type: "oidc",
      label: "Okta",
      issuer: "https://issuer.example.com",
      clientId: "demo-client",
      clientSecret: "notsecret-client",
      status: "active",
      domains: ["example.com"],
    });

    expect(client.POST).toHaveBeenCalledWith("/api/v1/admin/sso/providers", {
      body: {
        id: "okta",
        type: "oidc",
        label: "Okta",
        issuer: "https://issuer.example.com",
        clientId: "demo-client",
        clientSecret: "notsecret-client",
        status: "active",
        domains: ["example.com"],
      },
    });
  });

  it("updates provider", async () => {
    (client.PATCH as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        id: "okta",
      },
    });

    await updateSsoProvider("okta", {
      label: "Okta",
      issuer: "https://issuer.example.com",
      clientId: "demo-client",
      status: "active",
      domains: ["example.com"],
    });

    expect(client.PATCH).toHaveBeenCalledWith("/api/v1/admin/sso/providers/{id}", {
      params: { path: { id: "okta" } },
      body: {
        label: "Okta",
        issuer: "https://issuer.example.com",
        clientId: "demo-client",
        status: "active",
        domains: ["example.com"],
      },
    });
  });

  it("deletes provider", async () => {
    (client.DELETE as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({});

    await deleteSsoProvider("okta");

    expect(client.DELETE).toHaveBeenCalledWith("/api/v1/admin/sso/providers/{id}", {
      params: { path: { id: "okta" } },
    });
  });
});
