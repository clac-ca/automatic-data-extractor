import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AdminSettingsReadResponse } from "@/api/admin/settings";
import { ApiError } from "@/api/errors";
import { SettingsSaveBar } from "../SettingsSaveBar";
import { SettingsTechnicalDetails } from "../SettingsTechnicalDetails";
import {
  collectLockedEnvVars,
  findRuntimeSettingFieldError,
  formatRuntimeSettingsTimestamp,
  hasProblemCode,
} from "../runtimeSettingsUtils";

const settingsFixture: AdminSettingsReadResponse = {
  schemaVersion: 2,
  revision: 5,
  values: {
    safeMode: {
      enabled: false,
      detail: "Safe mode enabled.",
    },
    auth: {
      mode: "password_only",
      password: {
        resetEnabled: true,
        mfaRequired: false,
        complexity: {
          minLength: 12,
          requireUppercase: false,
          requireLowercase: false,
          requireNumber: false,
          requireSymbol: false,
        },
        lockout: {
          maxAttempts: 5,
          durationSeconds: 300,
        },
      },
      identityProvider: {
        provisioningMode: "jit",
      },
    },
  },
  meta: {
    safeMode: {
      enabled: {
        source: "db",
        lockedByEnv: false,
        envVar: "ADE_SAFE_MODE",
        restartRequired: false,
      },
      detail: {
        source: "env",
        lockedByEnv: true,
        envVar: "ADE_SAFE_MODE_DETAIL",
        restartRequired: true,
      },
    },
    auth: {
      mode: {
        source: "db",
        lockedByEnv: false,
        envVar: "ADE_AUTH_MODE",
        restartRequired: false,
      },
      password: {
        resetEnabled: {
          source: "env",
          lockedByEnv: true,
          envVar: "ADE_AUTH_PASSWORD_RESET_ENABLED",
          restartRequired: true,
        },
        mfaRequired: {
          source: "db",
          lockedByEnv: false,
          envVar: "ADE_AUTH_PASSWORD_MFA_REQUIRED",
          restartRequired: false,
        },
        complexity: {
          minLength: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_MIN_LENGTH",
            restartRequired: false,
          },
          requireUppercase: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_REQUIRE_UPPERCASE",
            restartRequired: false,
          },
          requireLowercase: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_REQUIRE_LOWERCASE",
            restartRequired: false,
          },
          requireNumber: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_REQUIRE_NUMBER",
            restartRequired: false,
          },
          requireSymbol: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_REQUIRE_SYMBOL",
            restartRequired: false,
          },
        },
        lockout: {
          maxAttempts: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_LOCKOUT_MAX_ATTEMPTS",
            restartRequired: false,
          },
          durationSeconds: {
            source: "db",
            lockedByEnv: false,
            envVar: "ADE_AUTH_PASSWORD_LOCKOUT_DURATION_SECONDS",
            restartRequired: false,
          },
        },
      },
      identityProvider: {
        provisioningMode: {
          source: "db",
          lockedByEnv: false,
          envVar: "ADE_AUTH_IDP_PROVISIONING_MODE",
          restartRequired: false,
        },
      },
    },
  },
  updatedAt: "2026-01-15T12:00:00Z",
  updatedBy: null,
};

describe("SettingsSaveBar", () => {
  it("does not render when not visible", () => {
    render(
      <SettingsSaveBar
        visible={false}
        canManage
        isSaving={false}
        canSave
        onSave={() => undefined}
        onDiscard={() => undefined}
      />,
    );

    expect(screen.queryByText("Save changes")).not.toBeInTheDocument();
  });

  it("triggers save/discard handlers and respects disabled states", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const onDiscard = vi.fn();

    const { rerender } = render(
      <SettingsSaveBar
        visible
        canManage
        isSaving={false}
        canSave
        onSave={onSave}
        onDiscard={onDiscard}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save changes" }));
    await user.click(screen.getByRole("button", { name: "Discard" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onDiscard).toHaveBeenCalledTimes(1);

    rerender(
      <SettingsSaveBar
        visible
        canManage={false}
        isSaving={false}
        canSave
        onSave={onSave}
        onDiscard={onDiscard}
      />,
    );

    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Discard" })).toBeDisabled();
  });
});

describe("SettingsTechnicalDetails", () => {
  it("is collapsed by default and expands on demand", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();

    render(<SettingsTechnicalDetails settings={settingsFixture} onRefresh={onRefresh} />);

    expect(screen.getByText("Technical details")).toBeInTheDocument();
    expect(screen.queryByText("Schema version")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByText("Schema version")).toBeInTheDocument();
    expect(screen.getByText("ADE_AUTH_PASSWORD_RESET_ENABLED")).toBeInTheDocument();
  });
});

describe("runtimeSettingsUtils", () => {
  it("collects sorted env locks and resolves field errors", () => {
    expect(collectLockedEnvVars(settingsFixture)).toEqual([
      "ADE_AUTH_PASSWORD_RESET_ENABLED",
      "ADE_SAFE_MODE_DETAIL",
    ]);

    expect(
      findRuntimeSettingFieldError(
        {
          "body.auth_password_mfaRequired": ["Invalid"],
          auth_password_resetEnabled: ["Nope"],
        },
        "auth.password.resetEnabled",
      ),
    ).toBe("Nope");
  });

  it("handles problem codes and timestamp formatting safely", () => {
    const error = new ApiError("conflict", 409, {
      type: "conflict",
      status: 409,
      title: "Conflict",
      instance: "/api/v1/admin/settings",
      errors: [
        {
          code: "settings_revision_conflict",
          message: "conflict",
        },
      ],
    });

    expect(hasProblemCode(error, "settings_revision_conflict")).toBe(true);
    expect(hasProblemCode(new Error("x"), "settings_revision_conflict")).toBe(false);
    expect(formatRuntimeSettingsTimestamp("not-a-date")).toBe("Unknown");
  });
});
