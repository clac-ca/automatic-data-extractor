import type { PresenceParticipant } from "@/types/presence";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AvatarGroup } from "@/components/ui/avatar-group";
import { Badge } from "@/components/ui/badge";
import { getInitials } from "@/lib/format";

export function DocumentPresenceBadges({
  participants,
}: {
  participants: PresenceParticipant[];
}) {
  if (!participants.length) return null;

  const avatarItems = participants.map((participant) => {
    const name = participant.display_name ?? undefined;
    const email = participant.email ?? undefined;
    return {
      id: participant.user_id,
      label: name || email || "Participant",
      initials: getInitials(name, email),
    };
  });

  return (
    <div className="mt-1 flex items-center gap-2">
      <Badge
        variant="secondary"
        className="px-1.5 py-0 text-[10px] uppercase tracking-wide text-muted-foreground"
      >
        Viewing
      </Badge>
      <AvatarGroup size={24} max={3}>
        {avatarItems.map((item) => (
          <Avatar key={item.id} aria-hidden="true" title={item.label}>
            <AvatarFallback className="text-[10px] font-semibold text-foreground">
              {item.initials}
            </AvatarFallback>
          </Avatar>
        ))}
      </AvatarGroup>
    </div>
  );
}
