import type { PresenceParticipant } from "@schema/presence";

import { DocumentPresenceBadges } from "../../presence/DocumentPresenceBadges";

export function DocumentNameCell({
  name,
  viewers,
}: {
  name: string;
  viewers: PresenceParticipant[];
}) {
  return (
    <div className="min-w-0 max-w-full">
      <div className="truncate font-medium" title={name}>
        {name}
      </div>
      <DocumentPresenceBadges participants={viewers} />
    </div>
  );
}
