import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CommentComposer } from "./CommentComposer";

const USER = {
  id: "user-1",
  name: "Ada Lovelace",
  email: "ada@example.com",
};

describe("CommentComposer", () => {
  it("submits on Enter", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(<CommentComposer mode="new" onSubmit={onSubmit} />);

    const textarea = screen.getByLabelText("Add a note...");
    fireEvent.change(textarea, { target: { value: "Hello there" } });
    fireEvent.keyDown(textarea, { key: "Enter" });

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        body: "Hello there",
        mentions: [],
      });
    });
  });

  it("does not submit on Shift+Enter", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(<CommentComposer mode="reply" onSubmit={onSubmit} />);

    const textarea = screen.getByLabelText("Write a reply...");
    fireEvent.change(textarea, { target: { value: "Line 1\n" } });
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: true });

    expect(onSubmit).not.toHaveBeenCalled();
    expect(textarea).toHaveValue("Line 1\n");
  });

  it("selects a mention from the popover before submit", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    render(
      <CommentComposer
        mode="new"
        mentionSuggestions={[USER]}
        onMentionQueryChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const textarea = screen.getByLabelText("Add a note...");
    fireEvent.change(textarea, {
      target: { value: "Hello @ad", selectionStart: 9, selectionEnd: 9 },
    });
    fireEvent.select(textarea, {
      target: { value: "Hello @ad", selectionStart: 9, selectionEnd: 9 },
    });

    expect(await screen.findByText('Mention results for "ad"')).toBeInTheDocument();

    fireEvent.keyDown(textarea, { key: "Enter" });

    await waitFor(() => {
      expect(textarea).toHaveValue("Hello @Ada Lovelace ");
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
