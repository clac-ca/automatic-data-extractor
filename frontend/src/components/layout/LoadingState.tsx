import { cn } from "@/lib/utils";

import { PageState } from "./PageState";

interface LoadingStateProps {
  readonly title: string;
  readonly className?: string;
}

export function LoadingState({ title, className }: LoadingStateProps) {
  return (
    <div className={cn("flex items-center justify-center px-6", className)}>
      <PageState title={title} variant="loading" />
    </div>
  );
}
