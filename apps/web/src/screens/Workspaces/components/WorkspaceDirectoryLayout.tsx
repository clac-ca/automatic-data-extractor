import { type ReactNode } from "react";
import { useNavigate } from "@app/nav/history";

import { useSession } from "@shared/auth/context/SessionContext";
import { GlobalTopBar } from "@app/shell/GlobalTopBar";
import { ProfileDropdown } from "@app/shell/ProfileDropdown";
import { DirectoryIcon } from "@screens/Workspace/components/workspace-navigation";

interface WorkspaceDirectoryLayoutProps {
  readonly children: ReactNode;
  readonly sidePanel?: ReactNode;
  readonly actions?: ReactNode;
}

export function WorkspaceDirectoryLayout({ children, sidePanel, actions }: WorkspaceDirectoryLayoutProps) {
  const session = useSession();
  const navigate = useNavigate();
  const displayName = session.user.display_name || session.user.email || "Signed in";
  const email = session.user.email ?? "";

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <GlobalTopBar
        leading={
          <button
            type="button"
            onClick={() => navigate("/workspaces")}
            className="focus-ring inline-flex items-center gap-3 rounded-xl border border-transparent bg-white px-3 py-2 text-left text-sm font-semibold text-slate-900 shadow-sm transition hover:border-slate-200"
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm">
              <DirectoryIcon className="h-5 w-5" aria-hidden />
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-slate-900">Workspace directory</span>
              <span className="text-xs text-slate-400">Automatic Data Extractor</span>
            </span>
          </button>
        }
        center={<DirectorySearchField />}
        trailing={
          <div className="flex items-center gap-2">
            {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
            <ProfileDropdown displayName={displayName} email={email} />
          </div>
        }
        maxWidthClassName="max-w-6xl"
      />
      <main className="flex flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl px-4 py-8">
          <div className={`grid gap-6 ${sidePanel ? "lg:grid-cols-[minmax(0,1fr)_280px]" : ""}`}>
            <div>{children}</div>
            {sidePanel ? <aside className="space-y-6">{sidePanel}</aside> : null}
          </div>
        </div>
      </main>
    </div>
  );
}

function DirectorySearchField() {
  return (
    <form
      role="search"
      className="hidden w-full max-w-md items-center rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm transition focus-within:border-brand-200 focus-within:ring-2 focus-within:ring-brand-100 md:flex"
      onSubmit={(event) => {
        event.preventDefault();
      }}
    >
      <label htmlFor="workspace-directory-search" className="sr-only">
        Search workspaces
      </label>
      <SearchIcon />
      <input
        id="workspace-directory-search"
        name="search"
        type="search"
        placeholder="Search workspaces"
        className="ml-3 w-full border-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-400 focus:outline-none"
      />
      <span className="text-xs text-slate-400">⌘K</span>
    </form>
  );
}

function SearchIcon() {
  return (
    <svg className="h-4 w-4 text-slate-400" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.6}>
      <circle cx="9" cy="9" r="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m13.5 13.5 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
