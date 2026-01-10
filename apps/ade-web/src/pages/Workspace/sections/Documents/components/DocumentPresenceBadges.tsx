import type { PresenceParticipant } from "@schema/presence";

import { AvatarStack, type AvatarStackItem } from "@/components/ui/avatar-stack";
import { Badge } from "@/components/ui/badge";

export function DocumentPresenceBadges({
  participants,
}: {
  participants: PresenceParticipant[];
}) {
  if (!participants.length) return null;

  const avatarItems = participants.map((participant) => ({
    id: participant.user_id,
    name: participant.display_name ?? undefined,
    email: participant.email ?? undefined,
  })) satisfies AvatarStackItem[];

  return (
    <div className="mt-1 flex items-center gap-2">
      <Badge
        variant="secondary"
        className="px-1.5 py-0 text-[10px] uppercase tracking-wide text-muted-foreground"
      >
        Viewing
      </Badge>
      <AvatarStack items={avatarItems} size="xs" max={3} />
    </div>
  );
}
