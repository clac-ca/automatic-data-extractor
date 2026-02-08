import { useMemo } from "react";
import { Check, Copy, ListFilter, Loader2, Pencil, Plus, Trash2 } from "lucide-react";

import type { DocumentViewRecord } from "@/api/documents/views";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

type ViewSection = {
  heading: "System" | "Public" | "Private";
  items: DocumentViewRecord[];
};

function visibilityLabel(view: DocumentViewRecord): "System" | "Public" | "Private" {
  if (view.visibility === "system") return "System";
  if (view.visibility === "public") return "Public";
  return "Private";
}

function allViews(sections: ViewSection[]) {
  return sections.flatMap((section) => section.items);
}

export function DocumentsViewsDropdown({
  systemViews,
  publicViews,
  privateViews,
  selectedViewId,
  isEdited = false,
  isLoading,
  isFetching,
  disabled = false,
  canMutateView,
  onSelectView,
  onCreateView,
  onRenameView,
  onDuplicateView,
  onDeleteView,
}: {
  systemViews: DocumentViewRecord[];
  publicViews: DocumentViewRecord[];
  privateViews: DocumentViewRecord[];
  selectedViewId: string | null;
  isEdited?: boolean;
  isLoading: boolean;
  isFetching: boolean;
  disabled?: boolean;
  canMutateView: (view: DocumentViewRecord) => boolean;
  onSelectView: (view: DocumentViewRecord) => void | Promise<void>;
  onCreateView: () => void;
  onRenameView: (view: DocumentViewRecord) => void;
  onDuplicateView: (view: DocumentViewRecord) => void;
  onDeleteView: (view: DocumentViewRecord) => void;
}) {
  const sections = useMemo<ViewSection[]>(
    () => [
      { heading: "System", items: systemViews },
      { heading: "Public", items: publicViews },
      { heading: "Private", items: privateViews },
    ],
    [privateViews, publicViews, systemViews],
  );

  const selectedView = useMemo(
    () => allViews(sections).find((view) => view.id === selectedViewId) ?? null,
    [sections, selectedViewId],
  );

  const hasViews = sections.some((section) => section.items.length > 0);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          aria-label="Select saved view"
          disabled={disabled}
        >
          <ListFilter className="h-4 w-4 text-muted-foreground" />
          <span>Views</span>
          {selectedView ? (
            <span className="max-w-[160px] truncate text-muted-foreground text-xs">
              {selectedView.name}
            </span>
          ) : null}
          {isFetching ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[380px] p-0" align="end">
        <div className="border-b px-3 py-2">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Active view</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="max-w-[210px] truncate text-sm font-medium">
              {selectedView?.name ?? "None selected"}
            </span>
            {selectedView ? (
              <Badge variant="secondary" className="h-5 text-[10px] uppercase tracking-wide">
                {visibilityLabel(selectedView)}
              </Badge>
            ) : null}
            {isEdited ? (
              <Badge variant="outline" className="h-5 text-[10px] uppercase tracking-wide">
                Edited
              </Badge>
            ) : null}
          </div>
        </div>

        <Command>
          <CommandInput placeholder="Search views..." />
          <CommandList>
            {isLoading ? (
              <CommandGroup>
                <CommandItem disabled>Loading views...</CommandItem>
              </CommandGroup>
            ) : null}
            {!isLoading && !hasViews ? <CommandEmpty>No views found.</CommandEmpty> : null}
            {sections.map((section) =>
              section.items.length > 0 ? (
                <CommandGroup key={section.heading} heading={section.heading}>
                  {section.items.map((view) => {
                    const canMutate = canMutateView(view);
                    return (
                      <CommandItem
                        key={view.id}
                        value={`${section.heading}:${view.name}`}
                        onSelect={() => {
                          void onSelectView(view);
                        }}
                        className="group"
                      >
                        <span className="truncate pr-2">{view.name}</span>
                        <Check
                          className={cn(
                            "ml-auto h-4 w-4",
                            selectedViewId === view.id ? "opacity-100" : "opacity-0",
                          )}
                        />
                        {canMutate ? (
                          <div className="ml-2 hidden items-center gap-0.5 group-hover:flex">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                onRenameView(view);
                              }}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6"
                              onClick={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                onDuplicateView(view);
                              }}
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 text-destructive hover:text-destructive"
                              onClick={(event) => {
                                event.preventDefault();
                                event.stopPropagation();
                                onDeleteView(view);
                              }}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        ) : null}
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              ) : null,
            )}
          </CommandList>
        </Command>

        <div className="border-t p-2">
          <Button type="button" variant="outline" size="sm" className="w-full" onClick={onCreateView}>
            <Plus className="h-4 w-4" />
            New view
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
