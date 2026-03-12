import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useDocumentActivityUiState } from "./useDocumentActivityUiState";

describe("useDocumentActivityUiState", () => {
  it("allows only one active reply or edit target at a time", () => {
    const { result } = renderHook(() =>
      useDocumentActivityUiState({
        createNote: vi.fn(),
        replyToItem: vi.fn(),
        editComment: vi.fn(),
      }),
    );

    act(() => {
      result.current.startReply({
        targetKey: "run:run-1",
        threadId: "thread-run",
      });
    });

    expect(result.current.activeReplyTarget?.targetKey).toBe("run:run-1");
    expect(result.current.activeEditCommentId).toBeNull();

    act(() => {
      result.current.startEdit("comment-1");
    });

    expect(result.current.activeReplyTarget).toBeNull();
    expect(result.current.activeEditCommentId).toBe("comment-1");

    act(() => {
      result.current.startReply({
        targetKey: "note:thread-note",
        threadId: "thread-note",
      });
    });

    expect(result.current.activeReplyTarget?.targetKey).toBe("note:thread-note");
    expect(result.current.activeEditCommentId).toBeNull();
  });

  it("keeps the reply open and stores an inline error when submit fails", async () => {
    const replyToItem = vi.fn().mockRejectedValue(new Error("Unable to save reply"));
    const { result } = renderHook(() =>
      useDocumentActivityUiState({
        createNote: vi.fn(),
        replyToItem,
        editComment: vi.fn(),
      }),
    );

    act(() => {
      result.current.startReply({
        targetKey: "document:doc-1",
        anchorType: "document",
        anchorId: "doc-1",
      });
    });

    await act(async () => {
      await expect(
        result.current.submitReply({
          targetKey: "document:doc-1",
          anchorType: "document",
          anchorId: "doc-1",
          body: "Hello",
          mentions: [],
        }),
      ).rejects.toThrow("Unable to save reply");
    });

    expect(result.current.activeReplyTarget?.targetKey).toBe("document:doc-1");
    await waitFor(() => {
      expect(result.current.replyErrorTargetKey).toBe("document:doc-1");
    });
  });

  it("preserves reply drafts across target switches and clears note errors when changing modes", async () => {
    const createNote = vi.fn().mockRejectedValue(new Error("Unable to save note"));
    const { result } = renderHook(() =>
      useDocumentActivityUiState({
        createNote,
        replyToItem: vi.fn(),
        editComment: vi.fn(),
      }),
    );

    await act(async () => {
      await expect(
        result.current.submitNote({
          body: "Decision pending",
          mentions: [],
        }),
      ).rejects.toThrow("Unable to save note");
    });

    expect(result.current.noteError).toBe("Unable to save note");

    act(() => {
      result.current.startReply({
        targetKey: "run:run-1",
        threadId: "thread-run-1",
      });
      result.current.setReplyDraft("run:run-1", {
        body: "Follow up on run 1",
        mentions: [],
      });
    });

    expect(result.current.noteError).toBeNull();
    expect(result.current.replyDraftsByTargetKey["run:run-1"]?.body).toBe("Follow up on run 1");

    act(() => {
      result.current.startReply({
        targetKey: "run:run-2",
        threadId: "thread-run-2",
      });
      result.current.setReplyDraft("run:run-2", {
        body: "Follow up on run 2",
        mentions: [],
      });
    });

    expect(result.current.replyDraftsByTargetKey["run:run-1"]?.body).toBe("Follow up on run 1");
    expect(result.current.replyDraftsByTargetKey["run:run-2"]?.body).toBe("Follow up on run 2");

    act(() => {
      result.current.startReply({
        targetKey: "run:run-1",
        threadId: "thread-run-1",
      });
    });

    expect(result.current.activeReplyTarget?.targetKey).toBe("run:run-1");
    expect(result.current.replyDraftsByTargetKey["run:run-1"]?.body).toBe("Follow up on run 1");
  });
});
