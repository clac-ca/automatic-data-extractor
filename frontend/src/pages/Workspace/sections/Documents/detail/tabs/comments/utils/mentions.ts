export type CommentComposerUser = {
  id: string;
  name?: string | null;
  email: string;
};

export type CommentComposerMention = CommentComposerUser & {
  start: number;
  end: number;
};

export type CommentComposerDraft = {
  body: string;
  mentions: CommentComposerMention[];
};

export type ActiveMentionQuery = {
  query: string;
  start: number;
  end: number;
};

type ChangeWindow = {
  start: number;
  previousEnd: number;
  nextEnd: number;
  delta: number;
};

const EMPTY_DRAFT: CommentComposerDraft = {
  body: "",
  mentions: [],
};

export function createEmptyCommentDraft(): CommentComposerDraft {
  return {
    body: EMPTY_DRAFT.body,
    mentions: [...EMPTY_DRAFT.mentions],
  };
}

export function getCommentComposerUserLabel(user: CommentComposerUser): string {
  return user.name?.trim() || user.email;
}

export function getMentionText(user: CommentComposerUser): string {
  return `@${getCommentComposerUserLabel(user)}`;
}

export function hasMeaningfulCommentBody(body: string): boolean {
  return body.trim().length > 0;
}

export function trimCommentDraft(draft: CommentComposerDraft): CommentComposerDraft {
  const trimmedBody = draft.body.trim();
  if (!trimmedBody) {
    return createEmptyCommentDraft();
  }

  const leadingWhitespace = draft.body.length - draft.body.trimStart().length;
  const trailingBoundary = draft.body.trimEnd().length;

  return {
    body: trimmedBody,
    mentions: sortMentions(
      draft.mentions.flatMap((mention) => {
        if (mention.start < leadingWhitespace || mention.end > trailingBoundary) {
          return [];
        }
        return [
          {
            ...mention,
            start: mention.start - leadingWhitespace,
            end: mention.end - leadingWhitespace,
          },
        ];
      }),
    ),
  };
}

export function sortMentions(mentions: CommentComposerMention[]): CommentComposerMention[] {
  return [...mentions].sort((left, right) => {
    if (left.start !== right.start) return left.start - right.start;
    if (left.end !== right.end) return left.end - right.end;
    return left.id.localeCompare(right.id);
  });
}

export function getActiveMentionQuery(body: string, caret: number): ActiveMentionQuery | null {
  const safeCaret = Math.max(0, Math.min(caret, body.length));
  const beforeCaret = body.slice(0, safeCaret);
  const match = /(^|[\s([{])@([^\s@]*)$/.exec(beforeCaret);

  if (!match) {
    return null;
  }

  return {
    query: match[2] ?? "",
    start: beforeCaret.length - (match[2]?.length ?? 0) - 1,
    end: safeCaret,
  };
}

export function reconcileCommentDraft(
  previousDraft: CommentComposerDraft,
  nextBody: string,
): CommentComposerDraft {
  if (previousDraft.body === nextBody) {
    return previousDraft;
  }

  const change = getChangeWindow(previousDraft.body, nextBody);
  const mentions = previousDraft.mentions.flatMap((mention) => {
    if (mention.end <= change.start) {
      return [mention];
    }

    if (mention.start >= change.previousEnd) {
      return [
        {
          ...mention,
          start: mention.start + change.delta,
          end: mention.end + change.delta,
        },
      ];
    }

    return [];
  });

  return {
    body: nextBody,
    mentions: sortMentions(
      mentions.filter((mention) => nextBody.slice(mention.start, mention.end) === getMentionText(mention)),
    ),
  };
}

export function insertMentionIntoDraft(
  draft: CommentComposerDraft,
  activeMention: ActiveMentionQuery,
  user: CommentComposerUser,
): {
  draft: CommentComposerDraft;
  selectionStart: number;
  selectionEnd: number;
} {
  const mentionText = getMentionText(user);
  const replacement = `${mentionText} `;
  const nextBody =
    `${draft.body.slice(0, activeMention.start)}${replacement}${draft.body.slice(activeMention.end)}`;
  const delta = replacement.length - (activeMention.end - activeMention.start);
  const mentionStart = activeMention.start;
  const mentionEnd = mentionStart + mentionText.length;

  const mentions = draft.mentions.flatMap((mention) => {
    if (mention.end <= activeMention.start) {
      return [mention];
    }

    if (mention.start >= activeMention.end) {
      return [
        {
          ...mention,
          start: mention.start + delta,
          end: mention.end + delta,
        },
      ];
    }

    return [];
  });

  mentions.push({
    ...user,
    name: user.name ?? null,
    start: mentionStart,
    end: mentionEnd,
  });

  const nextDraft = {
    body: nextBody,
    mentions: sortMentions(mentions),
  };

  return {
    draft: nextDraft,
    selectionStart: mentionEnd + 1,
    selectionEnd: mentionEnd + 1,
  };
}

function getChangeWindow(previousBody: string, nextBody: string): ChangeWindow {
  let start = 0;
  const minLength = Math.min(previousBody.length, nextBody.length);

  while (start < minLength && previousBody[start] === nextBody[start]) {
    start += 1;
  }

  let previousEnd = previousBody.length;
  let nextEnd = nextBody.length;

  while (
    previousEnd > start &&
    nextEnd > start &&
    previousBody[previousEnd - 1] === nextBody[nextEnd - 1]
  ) {
    previousEnd -= 1;
    nextEnd -= 1;
  }

  return {
    start,
    previousEnd,
    nextEnd,
    delta: nextEnd - previousEnd,
  };
}
