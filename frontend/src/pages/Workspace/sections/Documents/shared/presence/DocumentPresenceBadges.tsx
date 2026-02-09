import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AvatarGroup } from "@/components/ui/avatar-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DocumentPresenceEntry } from "@/pages/Workspace/hooks/presence/presenceParticipants";
import { getPresenceParticipantLabel } from "@/pages/Workspace/hooks/presence/presenceParticipants";

function formatSummary(entries: DocumentPresenceEntry[]) {
  const hasSelf = entries.some((entry) => entry.isCurrentUser);
  const othersCount = entries.filter((entry) => !entry.isCurrentUser).length;

  if (hasSelf && othersCount === 0) return "You";
  if (hasSelf) return `You + ${othersCount}`;
  return othersCount === 1 ? "1 viewing" : `${othersCount} viewing`;
}

function buildPresenceLabel(entry: DocumentPresenceEntry) {
  const base = entry.isCurrentUser ? "You" : getPresenceParticipantLabel(entry.participant);
  if (entry.tabCountForUser <= 1) return base;
  return `${base} (${entry.tabCountForUser} tabs)`;
}

export function DocumentPresenceBadges({
  entries,
  className,
}: {
  entries: DocumentPresenceEntry[];
  className?: string;
}) {
  if (!entries.length) return null;

  const summary = formatSummary(entries);
  const avatarItems = entries.map((entry) => {
    const name = entry.participant.display_name ?? undefined;
    const email = entry.participant.email ?? undefined;
    return {
      id: entry.participant.user_id || entry.participant.client_id,
      label: buildPresenceLabel(entry),
      initials: entry.isCurrentUser ? "You" : getInitials(name, email),
      isSelf: entry.isCurrentUser,
    };
  });
  const detailLabel = avatarItems.map((item) => item.label).join(", ");

  return (
    <div className={cn("mt-1 flex items-center gap-2", className)}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            data-row-interactive
            data-ignore-row-click
            className="inline-flex h-5 max-w-[180px] items-center gap-1.5 rounded-full border border-border/80 bg-muted/30 px-2 text-[10px] font-medium text-muted-foreground"
            aria-label={`${summary} in this document`}
          >
            <span
              aria-hidden
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                entries.some((entry) => entry.isCurrentUser) ? "bg-primary" : "bg-emerald-500",
              )}
            />
            <span className="truncate">{summary}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" align="start" className="max-w-[280px]">
          <p className="mb-2 text-xs font-medium">In this document</p>
          <div className="flex items-center gap-2">
            <AvatarGroup size={22} max={4}>
              {avatarItems.map((item) => (
                <Avatar key={item.id} aria-hidden="true" title={item.label}>
                  <AvatarFallback
                    className={cn(
                      "text-[10px] font-semibold",
                      item.isSelf ? "bg-primary/15 text-primary" : "text-foreground",
                    )}
                  >
                    {item.initials}
                  </AvatarFallback>
                </Avatar>
              ))}
            </AvatarGroup>
            <span className="text-xs text-muted-foreground">{detailLabel}</span>
          </div>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
