import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, LayoutDashboard, ShieldCheck, UserRound } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { fetchMfaStatus, type MfaStatusResponse } from "@/api/auth/api";
import { mapUiError } from "@/api/uiErrors";
import { PageState } from "@/components/layout";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { getInitials } from "@/lib/format";
import { useSession } from "@/providers/auth/SessionContext";
import { AccountShell, type AccountNavItem } from "./components/AccountShell";
import { AccountOverviewPage } from "./pages/AccountOverviewPage";
import { ApiKeysPage } from "./pages/ApiKeysPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SecurityPage } from "./pages/SecurityPage";

type AccountSectionId = "overview" | "profile" | "security" | "api-keys";

const BASE_SECTIONS: Array<{
  id: AccountSectionId;
  label: string;
  shortLabel: string;
  description: string;
  href: string;
  icon: AccountNavItem["icon"];
}> = [
  {
    id: "overview",
    label: "Overview",
    shortLabel: "Overview",
    description: "See account health and quick actions.",
    href: "/account",
    icon: LayoutDashboard,
  },
  {
    id: "profile",
    label: "Profile",
    shortLabel: "Profile",
    description: "Manage display name and identity details.",
    href: "/account/profile",
    icon: UserRound,
  },
  {
    id: "security",
    label: "Security",
    shortLabel: "Security",
    description: "Set up MFA and recovery options.",
    href: "/account/security",
    icon: ShieldCheck,
  },
  {
    id: "api-keys",
    label: "API Keys",
    shortLabel: "API Keys",
    description: "Create and revoke personal API credentials.",
    href: "/account/api-keys",
    icon: KeyRound,
  },
];

export default function AccountCenterScreen() {
  const session = useSession();
  const navigate = useNavigate();
  const params = useParams<{ "*": string }>();
  const { canManageApiKeys } = useGlobalPermissions();

  const [mfaStatus, setMfaStatus] = useState<MfaStatusResponse | null>(null);
  const [isMfaStatusLoading, setIsMfaStatusLoading] = useState(true);
  const [mfaStatusError, setMfaStatusError] = useState<string | null>(null);

  const rawPath = (params["*"] ?? "").trim();
  const segments = rawPath
    .split("/")
    .map((value) => value.trim())
    .filter((value) => value.length > 0);

  const activeSectionId: AccountSectionId =
    segments.length === 0
      ? "overview"
      : segments[0] === "profile"
        ? "profile"
        : segments[0] === "security"
          ? "security"
          : segments[0] === "api-keys"
            ? "api-keys"
            : "overview";

  const isInvalidPath = segments.length > 1 || !["", "profile", "security", "api-keys"].includes(segments[0] ?? "");

  useEffect(() => {
    if (isInvalidPath) {
      navigate("/account", { replace: true });
    }
  }, [isInvalidPath, navigate]);

  const refreshMfaStatus = useCallback(async () => {
    setMfaStatusError(null);
    try {
      const status = await fetchMfaStatus();
      setMfaStatus(status);
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to read MFA status right now.",
      });
      setMfaStatusError(mapped.message);
    } finally {
      setIsMfaStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMfaStatus();
  }, [refreshMfaStatus]);

  const navItems = useMemo(
    () =>
      BASE_SECTIONS.filter((section) => section.id !== "api-keys" || canManageApiKeys).map((section) => ({
        id: section.id,
        label: section.label,
        shortLabel: section.shortLabel,
        description: section.description,
        href: section.href,
        icon: section.icon,
      })),
    [canManageApiKeys],
  );

  const sectionMeta = useMemo(
    () => BASE_SECTIONS.find((section) => section.id === activeSectionId) ?? BASE_SECTIONS[0],
    [activeSectionId],
  );

  const displayName = session.user.display_name?.trim() || session.user.email || "Account";
  const email = session.user.email ?? "";
  const initials = getInitials(session.user.display_name, email);

  return (
    <AccountShell
      navItems={navItems}
      activeSectionId={sectionMeta.id}
      heading={sectionMeta.label}
      sectionDescription={sectionMeta.description}
      displayName={displayName}
      email={email}
      initials={initials}
    >
      {activeSectionId === "overview" ? (
        <AccountOverviewPage
          mfaStatus={mfaStatus}
          isMfaStatusLoading={isMfaStatusLoading}
          mfaStatusError={mfaStatusError}
          canManageApiKeys={canManageApiKeys}
        />
      ) : null}

      {activeSectionId === "profile" ? (
        <ProfilePage
          displayName={session.user.display_name}
          email={email}
          createdAt={session.user.created_at}
        />
      ) : null}

      {activeSectionId === "security" ? (
        <SecurityPage
          mfaStatus={mfaStatus}
          isMfaStatusLoading={isMfaStatusLoading}
          mfaStatusError={mfaStatusError}
          onRefreshMfaStatus={refreshMfaStatus}
        />
      ) : null}

      {activeSectionId === "api-keys" ? (
        canManageApiKeys ? (
          <ApiKeysPage />
        ) : (
          <PageState
            variant="error"
            title="You do not have access"
            description="API key management is restricted to global administrators in this release."
          />
        )
      ) : null}
    </AccountShell>
  );
}
