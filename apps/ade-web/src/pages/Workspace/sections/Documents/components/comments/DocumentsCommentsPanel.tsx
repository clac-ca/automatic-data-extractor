import { useMemo } from "react";

import { useSession } from "@/providers/auth/SessionContext";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import { CommentComposer } from "./CommentComposer";
import { useDocumentComments } from "../../hooks/useDocumentComments";
import { formatTimestamp } from "../../utils";
import type { DocumentRow } from "../../types";

type CommentAuthor = NonNullable<ReturnType<typeof useDocumentComments>["comments"][number]["author"]>;

function buildInitials(name: string) {
  const parts = name.split(/[\s_-]+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function renderCommentBody(
  body: string,
  mentions: Array<{ name: string | null; email: string | null }>,
) {
  const tokens = body.split(/(\s+)/);
  const mentionTokens = new Set<string>();
  mentions.forEach((mention) => {
    if (mention.name) {
      mentionTokens.add(`@${mention.name}`);
    }
    if (mention.email) {
      mentionTokens.add(`@${mention.email}`);
    }
  });

  return tokens.map((token, index) => {
    if (mentionTokens.has(token)) {
      return (
        <span
          key={`mention-${index}`}
          className="rounded bg-primary/10 px-1 text-primary"
        >
          {token}
        </span>
      );
    }
    return <span key={`token-${index}`}>{token}</span>;
  });
}

export function DocumentsCommentsPanel({
  workspaceId,
  document,
}: {
  workspaceId: string;
  document: DocumentRow;
}) {
  const session = useSession();
  const currentUser = useMemo<CommentAuthor>(
    () => ({
      id: session.user.id,
      name: session.user.display_name || session.user.email || null,
      email: session.user.email ?? null,
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );

  const {
    comments,
    isLoading,
    error,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
    submitComment,
    isSubmitting,
    submitError,
  } = useDocumentComments({
    workspaceId,
    documentId: document.id,
    currentUser,
  });

  const hasComments = comments.length > 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-1 overflow-auto px-6 py-3">
        {isLoading && !hasComments ? (
          <div className="space-y-3">
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex items-start gap-3">
                <Skeleton className="h-9 w-9 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            Unable to load comments. Refresh or try again later.
          </div>
        ) : hasComments ? (
          <div className="space-y-4">
            {comments.map((comment) => {
              const authorName =
                comment.author?.name || comment.author?.email || "Unknown";
              const initials = buildInitials(authorName);
              const timestamp = comment.optimistic
                ? "Sending…"
                : formatTimestamp(comment.createdAt);
              return (
                <div
                  key={comment.id}
                  className={comment.optimistic ? "opacity-70" : undefined}
                >
                  <div className="flex items-start gap-3">
                    <Avatar className="h-9 w-9">
                      <AvatarFallback className="text-xs font-semibold">
                        {initials}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-semibold text-foreground">
                          {authorName}
                        </span>
                        <span>{timestamp}</span>
                      </div>
                      <div className="mt-1 whitespace-pre-wrap text-sm text-foreground">
                        {renderCommentBody(comment.body, comment.mentions ?? [])}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
            No comments yet. Start the conversation below.
          </div>
        )}
        {hasNextPage ? (
          <div className="mt-4">
            <Button
              size="sm"
              variant="outline"
              onClick={() => fetchNextPage()}
              disabled={isFetchingNextPage}
            >
              {isFetchingNextPage ? "Loading..." : "Load more"}
            </Button>
          </div>
        ) : null}
      </div>
      <Separator />
      <div className="px-6 py-3">
        <CommentComposer
          workspaceId={workspaceId}
          currentUser={currentUser}
          onSubmit={submitComment}
          isSubmitting={isSubmitting}
        />
        {submitError ? (
          <div className="mt-2 text-xs text-destructive">
            {submitError}
          </div>
        ) : null}
      </div>
    </div>
  );
}
