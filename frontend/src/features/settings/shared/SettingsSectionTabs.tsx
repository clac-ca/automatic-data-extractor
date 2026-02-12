import { TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";

import type { SettingsSectionSpec } from "./types";

export function SettingsSectionTabs({
  sections,
  activeSectionId,
  onSectionChange,
}: {
  readonly sections: readonly SettingsSectionSpec[];
  readonly activeSectionId: string | null;
  readonly onSectionChange: (sectionId: string) => void;
}) {
  if (sections.length < 2 || !activeSectionId) {
    return null;
  }

  return (
    <TabsRoot value={activeSectionId} onValueChange={onSectionChange}>
      <TabsList className="flex flex-wrap gap-1 rounded-none border-b border-border/60 px-4">
        {sections.map((section) => (
          <TabsTrigger
            key={section.id}
            value={section.id}
            className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground aria-selected:bg-muted aria-selected:text-foreground"
          >
            {section.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </TabsRoot>
  );
}
