import type { PresenceParticipant } from "@schema/presence";

import { cn } from "@/lib/utils";

import { DocumentPresenceBadges } from "../../presence/DocumentPresenceBadges";

export function DocumentNameCell({
  name,
  viewers,
  isSelected = false,
  onOpen,
}: {
  name: string;
  viewers: PresenceParticipant[];
  isSelected?: boolean;
  onOpen?: () => void;
}) {
  const content = (
    <>
      <div
        className={cn(
          "truncate font-medium",
          isSelected && "text-foreground",
        )}
        title={name}
      >
        {name}
      </div>
      <DocumentPresenceBadges participants={viewers} />
    </>
  );

  if (!onOpen) {
    return <div className="min-w-0 max-w-full">{content}</div>;
  }

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "min-w-0 max-w-full text-left",
        isSelected ? "text-foreground" : "text-foreground/90",
      )}
      aria-pressed={isSelected}
    >
      {content}
    </button>
  );
}
