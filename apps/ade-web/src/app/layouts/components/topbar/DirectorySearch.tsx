import { useMemo, useState, type ReactNode } from "react";
import { generatePath, useNavigate } from "react-router-dom";

import { DirectoryIcon } from "@/components/icons";
import { useWorkspacesQuery } from "@/hooks/workspaces";
import {
  Search,
  SearchEmpty,
  SearchGroup,
  SearchInput,
  SearchItem,
  SearchList,
} from "@/components/ui/search";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";

type DirectorySearchItem = {
  id: string;
  label: string;
  description?: string;
  href: string;
  keywords?: string[];
};

export function DirectorySearch() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const workspacesQuery = useWorkspacesQuery();

  const items = useMemo<DirectorySearchItem[]>(() => {
    const workspaces = workspacesQuery.data?.items ?? [];
    return workspaces.map((workspace) => {
      const label = workspace.name?.trim() || "Workspace";
      return {
        id: workspace.id,
        label,
        description: workspace.slug ? `Slug: ${workspace.slug}` : "Workspace",
        keywords: workspace.slug ? [workspace.slug] : undefined,
        href: generatePath("/workspaces/:workspaceId/documents", {
          workspaceId: workspace.id,
        }),
      };
    });
  }, [workspacesQuery.data?.items]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Search className="w-full">
        <PopoverAnchor asChild>
          <div className="w-full">
            <SearchInput
              placeholder="Search workspaces..."
              onFocus={() => setOpen(true)}
              onValueChange={() => setOpen(true)}
            />
          </div>
        </PopoverAnchor>
        <PopoverContent
          data-slot="search-popover-content"
          align="start"
          sideOffset={8}
          className="w-[var(--radix-popover-trigger-width)] max-w-[min(32rem,var(--radix-popover-content-available-width))] p-0"
        >
          <SearchList>
            {workspacesQuery.isLoading ? (
              <SearchMessage>Loading workspaces...</SearchMessage>
            ) : workspacesQuery.isError ? (
              <SearchMessage tone="error">Search is unavailable right now.</SearchMessage>
            ) : (
              <>
                <SearchEmpty>
                  {items.length === 0 ? "No workspaces found." : "No matches."}
                </SearchEmpty>
                {items.length > 0 ? (
                  <SearchGroup heading="Workspaces">
                    {items.map((item) => (
                      <SearchItem
                        key={item.id}
                        value={item.label}
                        keywords={item.keywords}
                        onSelect={() => {
                          navigate(item.href);
                          setOpen(false);
                        }}
                      >
                        {renderDirectoryItem(item)}
                      </SearchItem>
                    ))}
                  </SearchGroup>
                ) : null}
              </>
            )}
          </SearchList>
        </PopoverContent>
      </Search>
    </Popover>
  );
}

function renderDirectoryItem(item: DirectorySearchItem) {
  return (
    <div className="flex min-w-0 items-start gap-3">
      <DirectoryIcon className="mt-0.5 h-4 w-4 text-muted-foreground" aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-sm font-semibold text-foreground">{item.label}</span>
        {item.description ? (
          <span className="truncate text-xs text-muted-foreground">{item.description}</span>
        ) : null}
      </div>
    </div>
  );
}

function SearchMessage({
  children,
  tone = "muted",
}: {
  readonly children: ReactNode;
  readonly tone?: "muted" | "error";
}) {
  return (
    <div
      className={
        tone === "error"
          ? "px-3 py-6 text-sm text-destructive"
          : "px-3 py-6 text-sm text-muted-foreground"
      }
    >
      {children}
    </div>
  );
}
