import type { DocumentComment } from "@/api/documents";

export type CommentAuthor = NonNullable<DocumentComment["author"]>;

export type ActivityCurrentUser = {
  id: string;
  name: string | null;
  email: string;
};

export type CommentMentionDraft = {
  user: CommentAuthor;
  start: number;
  end: number;
};

export type NoteDraft = {
  body: string;
  mentions: CommentMentionDraft[];
};

export type ThreadReplyDraft = {
  targetKey: string;
  threadId?: string | null;
  anchorType?: "document" | "run";
  anchorId?: string | null;
  body: string;
  mentions: CommentMentionDraft[];
};

export type CommentEditDraft = {
  commentId: string;
  body: string;
  mentions: CommentMentionDraft[];
};

export type ActivityReplyTarget = Pick<
  ThreadReplyDraft,
  "targetKey" | "threadId" | "anchorType" | "anchorId"
>;
