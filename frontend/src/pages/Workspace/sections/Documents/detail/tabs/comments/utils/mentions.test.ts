import { describe, expect, it } from "vitest";

import {
  getActiveMentionQuery,
  insertMentionIntoDraft,
  reconcileCommentDraft,
  trimCommentDraft,
  type CommentComposerDraft,
  type CommentComposerUser,
} from "./mentions";

const USER: CommentComposerUser = {
  id: "user-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
};

describe("comment mention utilities", () => {
  it("detects the active mention query at the caret", () => {
    const body = "Hello @ad";
    expect(getActiveMentionQuery(body, body.length)).toEqual({
      query: "ad",
      start: 6,
      end: 9,
    });
  });

  it("inserts a mention and records its range", () => {
    const initialDraft: CommentComposerDraft = {
      body: "Hello @ad",
      mentions: [],
    };

    const result = insertMentionIntoDraft(
      initialDraft,
      { query: "ad", start: 6, end: 9 },
      USER,
    );

    expect(result.draft).toEqual({
      body: "Hello @Ada Lovelace ",
      mentions: [
        {
          ...USER,
          start: 6,
          end: 19,
        },
      ],
    });
    expect(result.selectionStart).toBe(20);
    expect(result.selectionEnd).toBe(20);
  });

  it("shifts mention ranges when text is inserted before them", () => {
    const previousDraft: CommentComposerDraft = {
      body: "Hi @Ada Lovelace",
      mentions: [
        {
          ...USER,
          start: 3,
          end: 16,
        },
      ],
    };

    expect(reconcileCommentDraft(previousDraft, "Well, Hi @Ada Lovelace")).toEqual({
      body: "Well, Hi @Ada Lovelace",
      mentions: [
        {
          ...USER,
          start: 9,
          end: 22,
        },
      ],
    });
  });

  it("drops mentions when the user edits through the mention text", () => {
    const previousDraft: CommentComposerDraft = {
      body: "Hi @Ada Lovelace",
      mentions: [
        {
          ...USER,
          start: 3,
          end: 16,
        },
      ],
    };

    expect(reconcileCommentDraft(previousDraft, "Hi @Ada Lovel")).toEqual({
      body: "Hi @Ada Lovel",
      mentions: [],
    });
  });

  it("trims whitespace and adjusts mention ranges before submit", () => {
    const draft: CommentComposerDraft = {
      body: "  @Ada Lovelace says hi  ",
      mentions: [
        {
          ...USER,
          start: 2,
          end: 15,
        },
      ],
    };

    expect(trimCommentDraft(draft)).toEqual({
      body: "@Ada Lovelace says hi",
      mentions: [
        {
          ...USER,
          start: 0,
          end: 13,
        },
      ],
    });
  });
});
