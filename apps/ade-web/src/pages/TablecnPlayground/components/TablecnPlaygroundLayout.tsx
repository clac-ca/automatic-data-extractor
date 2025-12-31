import type * as React from "react";

import { cn } from "@components/tablecn/lib/utils";

interface TablecnPlaygroundLayoutProps extends React.ComponentProps<"div"> {
  title?: string;
  description?: string;
}

export function TablecnPlaygroundLayout({
  title = "Tablecn playground",
  description = "Minimal documents table (read-only).",
  children,
  className,
  ...props
}: TablecnPlaygroundLayoutProps) {
  return (
    <div
      className={cn("flex min-h-screen flex-col gap-4 p-6", className)}
      {...props}
    >
      <div>
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="text-muted-foreground text-sm">{description}</p>
      </div>
      {children}
    </div>
  );
}
