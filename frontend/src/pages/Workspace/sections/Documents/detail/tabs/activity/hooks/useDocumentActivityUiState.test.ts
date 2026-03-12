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
});
