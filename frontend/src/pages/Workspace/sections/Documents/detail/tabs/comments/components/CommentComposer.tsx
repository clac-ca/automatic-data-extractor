import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import {
  createEmptyCommentDraft,
  getActiveMentionQuery,
  getCommentComposerUserLabel,
  hasMeaningfulCommentBody,
  insertMentionIntoDraft,
  reconcileCommentDraft,
  trimCommentDraft,
  type CommentComposerDraft,
  type CommentComposerUser,
} from "../utils/mentions";

type Awaitable<T> = T | Promise<T>;
const EMPTY_MENTION_SUGGESTIONS: CommentComposerUser[] = [];

export type CommentComposerMode = "new" | "reply" | "edit";

type CommentComposerProps = {
  mode?: CommentComposerMode;
  variant?: "default" | "compact" | "editing";
  initialDraft?: CommentComposerDraft;
  draft?: CommentComposerDraft;
  onDraftChange?: (draft: CommentComposerDraft) => void;
  mentionSuggestions?: CommentComposerUser[];
  isMentionLoading?: boolean;
  onMentionQueryChange?: (query: string | null) => void;
  onSubmit: (draft: CommentComposerDraft) => Awaitable<unknown>;
  onCancel?: () => void;
  isSubmitting?: boolean;
  placeholder?: string;
  helperText?: string;
  shouldAutoFocus?: boolean;
  showHeading?: boolean;
  expandOnFocus?: boolean;
};

export function CommentComposer(props: CommentComposerProps) {
  const isControlled = props.draft !== undefined;
  const resetKey = useMemo(
    () => JSON.stringify({
      mode: props.mode ?? "new",
      body: props.initialDraft?.body ?? "",
      mentions: props.initialDraft?.mentions ?? [],
    }),
    [props.initialDraft, props.mode],
  );

  if (isControlled) {
    return <CommentComposerInner {...props} />;
  }

  return <CommentComposerInner key={resetKey} {...props} />;
}

function CommentComposerInner({
  mode = "new",
  variant = "default",
  initialDraft,
  draft: controlledDraft,
  onDraftChange,
  mentionSuggestions = EMPTY_MENTION_SUGGESTIONS,
  isMentionLoading = false,
  onMentionQueryChange,
  onSubmit,
  onCancel,
  isSubmitting = false,
  placeholder,
  helperText,
  shouldAutoFocus = false,
  showHeading = variant === "default",
  expandOnFocus = variant === "compact",
}: CommentComposerProps) {
  const anchorRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const pendingSelectionRef = useRef<{ start: number; end: number } | null>(null);
  const [uncontrolledDraft, setUncontrolledDraft] = useState<CommentComposerDraft>(
    initialDraft ?? createEmptyCommentDraft(),
  );
  const [caret, setCaret] = useState(() => (initialDraft?.body.length ?? 0));
  const [isFocused, setIsFocused] = useState(false);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState<{
    token: string | null;
    index: number;
  }>({
    token: null,
    index: 0,
  });
  const [dismissedMentionToken, setDismissedMentionToken] = useState<string | null>(null);
  const draft = controlledDraft ?? uncontrolledDraft;

  function updateDraft(
    nextDraft:
      | CommentComposerDraft
      | ((currentDraft: CommentComposerDraft) => CommentComposerDraft),
  ) {
    const resolvedDraft =
      typeof nextDraft === "function" ? nextDraft(draft) : nextDraft;

    if (controlledDraft) {
      onDraftChange?.(resolvedDraft);
      return;
    }

    setUncontrolledDraft(resolvedDraft);
  }

  useEffect(() => {
    const pendingSelection = pendingSelectionRef.current;
    if (!pendingSelection) return;
    pendingSelectionRef.current = null;
    textareaRef.current?.focus();
    textareaRef.current?.setSelectionRange(pendingSelection.start, pendingSelection.end);
  }, [draft.body]);

  useEffect(() => {
    if (!shouldAutoFocus) return;
    const frame = window.requestAnimationFrame(() => {
      textareaRef.current?.focus();
      const selectionStart = textareaRef.current?.value.length ?? 0;
      textareaRef.current?.setSelectionRange(selectionStart, selectionStart);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [shouldAutoFocus]);

  const activeMention = useMemo(
    () => getActiveMentionQuery(draft.body, caret),
    [draft.body, caret],
  );
  const mentionToken = activeMention
    ? `${activeMention.start}:${activeMention.end}:${activeMention.query}`
    : null;
  const mentionOpen = Boolean(activeMention) && dismissedMentionToken !== mentionToken;
  const highlightedIndex = mentionSuggestions.length === 0
    ? 0
    : highlightedSuggestion.token === mentionToken
      ? Math.min(highlightedSuggestion.index, mentionSuggestions.length - 1)
      : 0;

  useEffect(() => {
    if (!mentionOpen) {
      onMentionQueryChange?.(null);
      return;
    }

    onMentionQueryChange?.(activeMention?.query ?? "");
  }, [activeMention?.query, mentionOpen, onMentionQueryChange]);

  const canSubmit = hasMeaningfulCommentBody(draft.body) && !isSubmitting;
  const isExpanded =
    mode === "edit" || !expandOnFocus || isFocused || hasMeaningfulCommentBody(draft.body);
  const resolvedPlaceholder =
    placeholder ?? (
      mode === "edit"
        ? "Update your comment..."
        : mode === "reply"
          ? "Write a reply..."
          : "Add a note..."
    );
  const resolvedHelperText =
    helperText ?? (
      mode === "edit"
        ? "Use @ to mention someone. Enter saves, Shift+Enter adds a new line."
        : "Use @ to mention someone. Enter sends, Shift+Enter adds a new line."
    );
  const textareaRows =
    variant === "compact"
      ? isExpanded
        ? mode === "new"
          ? 4
          : 3
        : 2
      : mode === "new"
        ? 4
        : 3;

  async function handleSubmit() {
    if (!canSubmit) return;

    const nextDraft = trimCommentDraft(draft);
    if (!hasMeaningfulCommentBody(nextDraft.body)) return;

    try {
      await onSubmit(nextDraft);
    } catch {
      return;
    }

    if (mode === "new") {
      updateDraft(createEmptyCommentDraft());
      setCaret(0);
      setHighlightedSuggestion({ token: null, index: 0 });
      setDismissedMentionToken(null);
      pendingSelectionRef.current = { start: 0, end: 0 };
      return;
    }

    onCancel?.();
  }

  function selectMention(user: CommentComposerUser) {
    if (!activeMention) return;

    const inserted = insertMentionIntoDraft(draft, activeMention, user);
    updateDraft(inserted.draft);
    setCaret(inserted.selectionStart);
    setHighlightedSuggestion({ token: null, index: 0 });
    setDismissedMentionToken(null);
    pendingSelectionRef.current = {
      start: inserted.selectionStart,
      end: inserted.selectionEnd,
    };
  }

  function updateCaretFromTarget(target: HTMLTextAreaElement) {
    setCaret(target.selectionStart ?? target.value.length);
    setDismissedMentionToken(null);
  }

  async function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (mentionOpen && mentionSuggestions.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setHighlightedSuggestion({
          token: mentionToken,
          index: (highlightedIndex + 1) % mentionSuggestions.length,
        });
        return;
      }

      if (event.key === "ArrowUp") {
        event.preventDefault();
        setHighlightedSuggestion({
          token: mentionToken,
          index: highlightedIndex === 0 ? mentionSuggestions.length - 1 : highlightedIndex - 1,
        });
        return;
      }

      if (!event.shiftKey && (event.key === "Enter" || event.key === "Tab")) {
        event.preventDefault();
        selectMention(mentionSuggestions[highlightedIndex] ?? mentionSuggestions[0]);
        return;
      }
    }

    if (mentionOpen && event.key === "Escape") {
      event.preventDefault();
      setDismissedMentionToken(mentionToken);
      return;
    }

    if (event.key === "Escape" && onCancel && mode !== "new") {
      event.preventDefault();
      onCancel();
      return;
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await handleSubmit();
    }
  }

  return (
    <div
      className={cn(
        "flex flex-col",
        variant === "compact" ? "gap-2" : "gap-3",
      )}
    >
      {showHeading ? (
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="font-medium text-sm text-foreground">
              {mode === "edit" ? "Editing comment" : mode === "reply" ? "Replying in thread" : "Add note"}
            </div>
            <div className="text-xs text-muted-foreground">{resolvedHelperText}</div>
          </div>
        </div>
      ) : null}

      <Popover open={mentionOpen} modal={false}>
        <PopoverAnchor asChild>
          <div ref={anchorRef} className="relative">
            <textarea
              ref={textareaRef}
              value={draft.body}
              placeholder={resolvedPlaceholder}
              aria-label={resolvedPlaceholder}
              rows={textareaRows}
              className={cn(
                "w-full resize-y border border-input bg-background px-3 py-2 text-sm shadow-xs outline-hidden transition-colors",
                "placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring",
                variant === "editing"
                  ? "min-h-24 rounded-md border-border/80"
                  : variant === "compact"
                    ? cn(
                        "rounded-md border-border/80",
                        isExpanded ? "min-h-20" : "min-h-14",
                      )
                    : "min-h-28 rounded-lg",
              )}
              onChange={(event) => {
                updateDraft((current) => reconcileCommentDraft(current, event.target.value));
                updateCaretFromTarget(event.target);
              }}
              onClick={(event) => updateCaretFromTarget(event.currentTarget)}
              onFocus={(event) => {
                setIsFocused(true);
                updateCaretFromTarget(event.currentTarget);
              }}
              onBlur={() => setIsFocused(false)}
              onSelect={(event) => updateCaretFromTarget(event.currentTarget)}
              onKeyDown={(event) => {
                void handleKeyDown(event);
              }}
              disabled={isSubmitting}
            />
          </div>
        </PopoverAnchor>

        <PopoverContent
          align="start"
          sideOffset={8}
          className="w-[min(24rem,calc(100vw-2rem))] max-w-[min(24rem,var(--radix-popover-content-available-width))] p-0"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            textareaRef.current?.focus();
          }}
          onInteractOutside={(event) => {
            const target = event.target as HTMLElement | null;
            if (target && anchorRef.current?.contains(target)) {
              event.preventDefault();
            }
          }}
        >
          <Command shouldFilter={false}>
            <div className="border-b px-3 py-2 text-[11px] text-muted-foreground">
              {activeMention?.query
                ? `Mention results for "${activeMention.query}"`
                : "Mention a workspace member"}
            </div>
            <CommandList className="max-h-[min(18rem,var(--radix-popover-content-available-height))] p-1">
              {isMentionLoading ? (
                <div className="px-3 py-2 text-sm text-muted-foreground">Loading members...</div>
              ) : mentionSuggestions.length === 0 ? (
                <CommandEmpty>No matches found.</CommandEmpty>
              ) : (
                <CommandGroup heading="Workspace members">
                  {mentionSuggestions.map((suggestion, index) => {
                    const isActive = index === highlightedIndex;
                    return (
                      <CommandItem
                        key={suggestion.id}
                        value={suggestion.id}
                        className={cn(
                          "items-start gap-3 rounded-md px-3 py-2",
                          isActive && "bg-accent text-accent-foreground",
                        )}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          selectMention(suggestion);
                        }}
                        onSelect={() => selectMention(suggestion)}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium text-sm">
                            {getCommentComposerUserLabel(suggestion)}
                          </span>
                          <span className="block truncate text-xs text-muted-foreground">
                            {suggestion.email}
                          </span>
                        </span>
                        <CommandShortcut>Enter</CommandShortcut>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      <div className="flex items-center justify-between gap-3">
        <div className="text-xs text-muted-foreground">Enter sends. Shift+Enter adds a new line.</div>
        <div className="flex items-center gap-2">
          {onCancel ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant={mode === "edit" ? "outline" : "default"}
            onClick={() => void handleSubmit()}
            disabled={!canSubmit}
          >
            {isSubmitting
              ? mode === "edit"
                ? "Saving..."
                : "Sending..."
              : mode === "edit"
                ? "Save"
                : mode === "reply"
                  ? "Reply"
                  : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export type {
  CommentComposerDraft,
  CommentComposerMention,
  CommentComposerUser,
} from "../utils/mentions";
