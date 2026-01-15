import { useState } from "react";

import { AppearanceMenu } from "@/components/navigation/AppearanceMenu";
import { AboutVersionsModal } from "@/components/navigation/AboutVersionsModal";
import { ProfileDropdown } from "@/components/navigation/ProfileDropdown";
import { useSession } from "@/providers/auth/SessionContext";

export function AppTopBarControls() {
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
