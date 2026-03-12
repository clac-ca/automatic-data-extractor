import { describe, expect, it } from "vitest";

import {
  codePointIndexFromCodeUnitIndex,
  codeUnitIndexFromCodePointIndex,
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

  it("preserves mention ranges when unrelated edits keep the original mention text intact", () => {
    const previousDraft: CommentComposerDraft = {
      body: "Hi @Ada Lovelace",
      mentions: [
        {
          ...USER,
          name: "Ada Byron",
          start: 3,
          end: 16,
        },
      ],
    };

    expect(reconcileCommentDraft(previousDraft, "Hi team, @Ada Lovelace")).toEqual({
      body: "Hi team, @Ada Lovelace",
      mentions: [
        {
          ...USER,
          name: "Ada Byron",
          start: 9,
          end: 22,
        },
      ],
    });
  });

  it("converts mention offsets between code units and code points", () => {
    const body = "😀 hi @Ada";

    expect(codePointIndexFromCodeUnitIndex(body, 5)).toBe(4);
    expect(codePointIndexFromCodeUnitIndex(body, 9)).toBe(8);
    expect(codeUnitIndexFromCodePointIndex(body, 4)).toBe(5);
    expect(codeUnitIndexFromCodePointIndex(body, 8)).toBe(9);
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
