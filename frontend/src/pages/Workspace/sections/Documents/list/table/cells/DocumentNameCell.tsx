import type { PresenceParticipant } from "@/types/presence";

import { cn } from "@/lib/utils";

import { DocumentPresenceBadges } from "../../../shared/presence/DocumentPresenceBadges";

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
      <div className="flex min-w-0 items-start gap-2">
        <div className="min-w-0">
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
        </div>
      </div>
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
