import { useState } from "react";

import { AppearanceMenu } from "@/app/layouts/components/topbar/actions/AppearanceMenu";
import { AboutVersionsModal } from "@/app/layouts/components/topbar/actions/AboutVersionsModal";
import { ProfileDropdown } from "@/app/layouts/components/topbar/actions/ProfileDropdown";
import { openReleaseNotes } from "@/config/release-notes";
import { useSession } from "@/providers/auth/SessionContext";

export function TopbarControls() {
  const session = useSession();
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <>
      <AboutVersionsModal open={isVersionsModalOpen} onClose={() => setIsVersionsModalOpen(false)} />
      <div className="flex min-w-0 flex-nowrap items-center gap-2">
        <AppearanceMenu tone="header" />
        <ProfileDropdown
          displayName={displayName}
          email={email}
          tone="header"
          actions={[
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
          ]}
        />
      </div>
    </>
  );
}
