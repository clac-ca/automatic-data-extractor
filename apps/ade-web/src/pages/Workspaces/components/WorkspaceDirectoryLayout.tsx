import { useState, type ReactNode } from "react";
import { useNavigate } from "@app/navigation/history";

import { useSession } from "@components/providers/auth/SessionContext";
import { AppearanceMenu } from "@components/shell/AppearanceMenu";
import { GlobalTopBar, type GlobalTopBarSearchProps } from "@components/shell/GlobalTopBar";
import { ProfileDropdown } from "@components/shell/ProfileDropdown";
import { AboutVersionsModal } from "@components/shell/AboutVersionsModal";
import { DirectoryIcon } from "@components/icons";

interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly sidePanel?: ReactNode;
  readonly actions?: ReactNode;
  readonly search?: GlobalTopBarSearchProps;
}

export function WorkspaceDirectoryLayout({ children, sidePanel, actions, search }: WorkspaceDirectoryLayoutProps) {
  const session = useSession();
  const navigate = useNavigate();
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <>
      <AboutVersionsModal open={isVersionsModalOpen} onClose={() => setIsVersionsModalOpen(false)} />
      <div className="flex min-h-screen flex-col bg-background text-foreground">
        <GlobalTopBar
          brand={
            <button
              type="button"
              onClick={() => navigate("/workspaces")}
              className="focus-ring inline-flex items-center gap-3 rounded-xl border border-header-border/40 bg-header/20 px-3 py-2 text-left text-sm font-semibold text-header-foreground transition hover:border-header-border/70 hover:bg-header/30"
            >
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-on-brand shadow-sm">
                <DirectoryIcon className="h-5 w-5" aria-hidden />
              </span>
              <span className="flex flex-col leading-tight">
                <span className="text-sm font-semibold text-header-foreground">Workspace directory</span>
                <span className="text-xs text-header-muted">Automatic Data Extractor</span>
              </span>
            </button>
          }
          search={search}
          actions={actions ? <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div> : undefined}
          trailing={
            <div className="flex min-w-0 flex-wrap items-center gap-2">
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
          }
        />
        <main id="main-content" tabIndex={-1} className="flex flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-6xl px-4 py-8">
            <div className={`grid gap-6 ${sidePanel ? "lg:grid-cols-[minmax(0,1fr)_280px]" : ""}`}>
              <div>{children}</div>
              {sidePanel ? <aside className="space-y-6">{sidePanel}</aside> : null}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
