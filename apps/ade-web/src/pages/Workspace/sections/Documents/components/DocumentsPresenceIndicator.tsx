import type { PresenceConnectionState, PresenceParticipant } from "@schema/presence";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AvatarGroup } from "@/components/ui/avatar-group";
import { Badge } from "@/components/ui/badge";
import { getInitials } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATE_LABELS: Record<PresenceConnectionState, string> = {
  idle: "Offline",
  connecting: "Connecting",
  open: "Live",
  closed: "Offline",
};

const STATE_DOT_CLASSES: Record<PresenceConnectionState, string> = {
  idle: "bg-muted-foreground/40",
  connecting: "bg-accent-foreground/60 animate-pulse",
  open: "bg-primary",
  closed: "bg-muted-foreground/40",
};

export function DocumentsPresenceIndicator({
  participants,
  connectionState,
  className,
}: {
  participants: PresenceParticipant[];
  connectionState: PresenceConnectionState;
  className?: string;
}) {
  const avatarItems = participants.map((participant) => {
    const name = participant.display_name ?? undefined;
    const email = participant.email ?? undefined;
    return {
      id: participant.user_id,
      label: name || email || "Participant",
      initials: getInitials(name, email),
    };
  });

  const label = STATE_LABELS[connectionState] ?? "Offline";
  const countLabel = participants.length === 0 ? "Just you" : `${participants.length} viewing`;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Badge variant="outline" className="gap-2 border-muted-foreground/20 text-muted-foreground">
        <span
          aria-hidden
          className={cn("h-2 w-2 rounded-full", STATE_DOT_CLASSES[connectionState])}
        />
        {label}
      </Badge>
      <span className="text-xs text-muted-foreground">{countLabel}</span>
      {participants.length > 0 ? (
        <AvatarGroup size={24} max={4}>
          {avatarItems.map((item) => (
            <Avatar key={item.id} aria-hidden="true" title={item.label}>
              <AvatarFallback className="text-[10px] font-semibold text-foreground">
                {item.initials}
              </AvatarFallback>
            </Avatar>
          ))}
        </AvatarGroup>
      ) : null}
    </div>
  );
}
