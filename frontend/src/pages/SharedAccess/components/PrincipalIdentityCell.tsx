import clsx from "clsx";
import { UserRound, Users } from "lucide-react";
import type { ReactNode } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { getInitials } from "@/lib/format";

interface PrincipalIdentityCellProps {
  readonly principalType: "user" | "group";
  readonly title: string;
  readonly subtitle?: string | null;
  readonly detail?: string | null;
  readonly trailing?: ReactNode;
  readonly className?: string;
}

export function PrincipalIdentityCell({
  principalType,
  title,
  subtitle,
  detail,
  trailing,
  className,
}: PrincipalIdentityCellProps) {
  const initials = getInitials(title, subtitle ?? undefined);

  return (
    <div className={clsx("flex min-w-0 items-start gap-3", className)}>
      <Avatar aria-hidden="true" className="mt-0.5 h-9 w-9 border border-border bg-muted/30">
        <AvatarFallback className="text-xs font-semibold text-foreground">
          {principalType === "group" ? <Users className="h-4 w-4" /> : initials}
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex min-w-0 items-center gap-2">
          <p className="truncate font-semibold text-foreground">{title}</p>
          {principalType === "user" ? (
            <UserRound aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <Users aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          )}
        </div>
        {subtitle ? <p className="truncate text-xs text-muted-foreground">{subtitle}</p> : null}
        {detail ? <p className="truncate text-xs text-muted-foreground">{detail}</p> : null}
      </div>
      {trailing ? <div className="shrink-0">{trailing}</div> : null}
    </div>
  );
}

