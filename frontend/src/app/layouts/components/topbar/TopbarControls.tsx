import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { AppearanceMenu } from "@/app/layouts/components/topbar/actions/AppearanceMenu";
import { AboutVersionsModal } from "@/app/layouts/components/topbar/actions/AboutVersionsModal";
import { ProfileDropdown } from "@/app/layouts/components/topbar/actions/ProfileDropdown";
import { openReleaseNotes } from "@/config/release-notes";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useSession } from "@/providers/auth/SessionContext";

export function TopbarControls() {
  const session = useSession();
  const navigate = useNavigate();
  const { canAccessOrganizationSettings } = useGlobalPermissions();
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";
  const actions = [
    ...(canAccessOrganizationSettings
      ? [
          {
            id: "organization-settings",
            label: "Organization Settings",
            description: "Users, roles, API keys, and system controls",
            onSelect: () => navigate("/organization/settings"),
          },
        ]
      : []),
    {
      id: "release-notes",
      label: "Release notes",
      description: "GitHub releases + changelog",
      onSelect: openReleaseNotes,
    },
    {
      id: "about-versions",
      label: "About / Versions",
      description: "ade-web, ade-api, ade-engine",
      onSelect: () => setIsVersionsModalOpen(true),
    },
  ];

  return (
    <>
      <AboutVersionsModal open={isVersionsModalOpen} onClose={() => setIsVersionsModalOpen(false)} />
      <div className="flex min-w-0 flex-nowrap items-center gap-2">
        <AppearanceMenu tone="header" />
        <ProfileDropdown
          displayName={displayName}
          email={email}
          tone="header"
          actions={actions}
        />
      </div>
    </>
  );
}
