import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

import type { ActivityItem } from "../model";
import { DocumentActivityFeedItem } from "./DocumentActivityFeedItem";

export function DocumentActivityFeed({
  items,
  isLoading,
  hasError,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
}: {
  items: ActivityItem[];
  isLoading: boolean;
  hasError: boolean;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onLoadMore: () => void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-auto px-4 py-4">
      {hasError ? (
        <div className="mb-4 rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
          Some activity may be missing right now.
        </div>
      ) : null}

      {isLoading ? <LoadingState /> : null}
      {!isLoading && items.length === 0 ? <EmptyState /> : null}
      {!isLoading && items.length > 0 ? (
        <div className="space-y-3">
          {items.map((item) => (
            <DocumentActivityFeedItem key={item.key} item={item} />
          ))}
        </div>
      ) : null}

      {hasNextPage ? (
        <div className="mt-4">
          <Button size="sm" variant="outline" onClick={onLoadMore} disabled={isFetchingNextPage}>
            {isFetchingNextPage ? "Loading..." : "Load more comments"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-start gap-3">
          <Skeleton className="mt-1 h-8 w-8 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-44" />
            <Skeleton className="h-4 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-border bg-background p-4 text-sm text-muted-foreground">
      No activity found for this filter.
    </div>
  );
}
