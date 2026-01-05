import type { PresenceConnectionState, PresenceParticipant } from "@schema/presence";

import { AvatarStack, type AvatarStackItem } from "@/components/ui/avatar-stack";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATE_LABELS: Record<PresenceConnectionState, string> = {
  idle: "Offline",
  connecting: "Connecting",
  open: "Live",
  closed: "Offline",
};

const STATE_DOT_CLASSES: Record<PresenceConnectionState, string> = {
  idle: "bg-muted-foreground/40",
  connecting: "bg-amber-400 animate-pulse",
  open: "bg-emerald-500",
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
  const avatarItems = participants.map((participant) => ({
    id: participant.user_id,
    name: participant.display_name ?? undefined,
    email: participant.email ?? undefined,
  })) satisfies AvatarStackItem[];

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
      {participants.length > 0 ? <AvatarStack items={avatarItems} size="xs" max={4} /> : null}
    </div>
  );
}
