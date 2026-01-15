import { useCallback, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { listWorkspaceMembers } from "@/api/workspaces/api";
import { Button } from "@/components/ui/button";
import { Mention, MentionContent, MentionInput, MentionItem, MentionLabel } from "@/components/ui/mention";

import { shortId } from "../../utils";
import type { CommentDraft } from "../../hooks/useDocumentComments";

type CommentUser = {
  id: string;
  name: string | null;
  email: string | null;
};

export function CommentComposer({
  workspaceId,
  currentUser,
  onSubmit,
  isSubmitting = false,
}: {
  workspaceId: string;
  currentUser: CommentUser;
  onSubmit: (draft: CommentDraft) => void;
  isSubmitting?: boolean;
}) {
  const [inputValue, setInputValue] = useState("");
  const [mentionOpen, setMentionOpen] = useState(false);
  const [selectedMentionIds, setSelectedMentionIds] = useState<string[]>([]);

  const membersQuery = useQuery({
    queryKey: ["comment-mentions", workspaceId],
    queryFn: ({ signal }) =>
      listWorkspaceMembers(workspaceId, {
        limit: 20,
        signal,
      }),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
    placeholderData: (previous) => previous,
  });

  const mentionOptions = useMemo(() => {
    const members = membersQuery.data?.items ?? [];
    return members.map((member) => {
      const id = member.user_id;
      const name = member.user?.display_name || member.user?.email || null;
      const fallback = shortId(id);
      const label =
        id === currentUser.id
          ? currentUser.name || currentUser.email || name || fallback
          : name || fallback;
      return { id, label, email: member.user?.email ?? null };
    });
  }, [currentUser.email, currentUser.id, currentUser.name, membersQuery.data?.items]);

  const mentionsById = useMemo(() => {
    const map = new Map<string, CommentUser>();
    mentionOptions.forEach((option) => {
      map.set(option.id, {
        id: option.id,
        name: option.label ?? null,
        email: option.email ?? null,
      });
    });
    return map;
  }, [mentionOptions]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter" && !mentionOpen) {
        event.preventDefault();
        if (!inputValue.trim()) return;
        const mentions = selectedMentionIds
          .map((id) => mentionsById.get(id))
          .filter(Boolean) as CommentUser[];
        onSubmit({ body: inputValue.trim(), mentions });
        setInputValue("");
        setSelectedMentionIds([]);
      }
    },
    [inputValue, mentionOpen, mentionsById, onSubmit, selectedMentionIds],
  );

  const canSubmit = inputValue.trim().length > 0 && !isSubmitting;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex w-full flex-col gap-2">
        <Mention
          value={selectedMentionIds}
          onValueChange={setSelectedMentionIds}
          open={mentionOpen}
          onOpenChange={setMentionOpen}
          inputValue={inputValue}
          onInputValueChange={setInputValue}
          trigger="@"
        >
          <MentionLabel className="sr-only">Add a comment</MentionLabel>
          <MentionInput
            placeholder="Add a comment…"
            aria-label="Add a comment"
            onKeyDown={handleKeyDown}
          />
          <MentionContent>
            {membersQuery.isLoading ? (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">Loading members…</div>
            ) : mentionOptions.length === 0 ? (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">No matches</div>
            ) : (
              mentionOptions.map((option) => (
                <MentionItem key={option.id} value={option.id} label={option.label}>
                  <span>{option.label}</span>
                  {option.email ? (
                    <span className="text-[11px] text-muted-foreground">{option.email}</span>
                  ) : null}
                </MentionItem>
              ))
            )}
          </MentionContent>
        </Mention>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Enter to send</span>
          <Button
            size="sm"
            onClick={() => {
              if (!canSubmit) return;
              const mentions = selectedMentionIds
                .map((id) => mentionsById.get(id))
                .filter(Boolean) as CommentUser[];
              onSubmit({ body: inputValue.trim(), mentions });
              setInputValue("");
              setSelectedMentionIds([]);
            }}
            disabled={!canSubmit}
          >
            {isSubmitting ? "Sending..." : "Send"}
          </Button>
        </div>
      </div>
      <div className="text-[11px] text-muted-foreground">
        Comments are shared with workspace members. @mention someone to notify them.
      </div>
    </div>
  );
}
