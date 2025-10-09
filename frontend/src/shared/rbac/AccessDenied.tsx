import type { ReactNode } from "react";

interface AccessDeniedProps {
  children?: ReactNode;
}

export function AccessDenied({ children }: AccessDeniedProps) {
  return (
    <div className="rounded border border-amber-500/40 bg-amber-500/10 p-6 text-sm text-amber-100">
      {children ?? "You do not have permission to view this area."}
    </div>
  );
}
