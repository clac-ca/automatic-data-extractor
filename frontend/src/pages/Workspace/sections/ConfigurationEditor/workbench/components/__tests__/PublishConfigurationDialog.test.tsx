import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PublishConfigurationDialog } from "../PublishConfigurationDialog";
import { WorkbenchConsoleStore } from "../../state/consoleStore";

function buildConsoleStore() {
  const store = new WorkbenchConsoleStore(64);
  store.append({
    level: "info",
    message: "Publish started",
    timestamp: "2026-02-07T10:00:00.000Z",
    origin: "run",
  });
  return store;
}

describe("PublishConfigurationDialog", () => {
  it("renders confirm phase details", () => {
    render(
      <PublishConfigurationDialog
        open
        phase="confirm"
        isDirty
        canPublish
        console={buildConsoleStore()}
        activeConfigurationName="Current Active"
        onCancel={vi.fn()}
        onStartPublish={vi.fn()}
        onDone={vi.fn()}
        onRetryPublish={vi.fn()}
        onDuplicateToEdit={vi.fn()}
      />,
    );

    expect(screen.getByText("Publish this draft configuration?")).toBeInTheDocument();
    expect(screen.getByText("This configuration becomes active for newly uploaded documents by default.")).toBeInTheDocument();
    expect(screen.getByText("Unsaved changes will be saved before publish starts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish configuration" })).toBeEnabled();
  });

  it("renders running phase stream status and blocks close actions", () => {
    const onCancel = vi.fn();
    render(
      <PublishConfigurationDialog
        open
        phase="running"
        isDirty={false}
        canPublish={false}
        runId="run-123"
        connectionState="reconnecting"
        console={buildConsoleStore()}
        onCancel={onCancel}
        onStartPublish={vi.fn()}
        onDone={vi.fn()}
        onRetryPublish={vi.fn()}
        onDuplicateToEdit={vi.fn()}
      />,
    );

    expect(screen.getByText("Publishing configuration")).toBeInTheDocument();
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
    expect(screen.getByText("Waiting for publish events…")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close publish dialog" }));
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("renders succeeded phase actions", () => {
    const onDone = vi.fn();
    const onDuplicateToEdit = vi.fn();
    render(
      <PublishConfigurationDialog
        open
        phase="succeeded"
        isDirty={false}
        canPublish={false}
        console={buildConsoleStore()}
        onCancel={vi.fn()}
        onStartPublish={vi.fn()}
        onDone={onDone}
        onRetryPublish={vi.fn()}
        onDuplicateToEdit={onDuplicateToEdit}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    fireEvent.click(screen.getByRole("button", { name: "Duplicate to edit" }));

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(onDuplicateToEdit).toHaveBeenCalledTimes(1);
  });

  it("renders failure message and retry action", () => {
    const onRetryPublish = vi.fn();
    render(
      <PublishConfigurationDialog
        open
        phase="failed"
        isDirty={false}
        canPublish
        errorMessage="Publish failed: stale snapshot"
        console={buildConsoleStore()}
        onCancel={vi.fn()}
        onStartPublish={vi.fn()}
        onDone={vi.fn()}
        onRetryPublish={onRetryPublish}
        onDuplicateToEdit={vi.fn()}
      />,
    );

    expect(screen.getByText("Publish failed: stale snapshot")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry publish" }));
    expect(onRetryPublish).toHaveBeenCalledTimes(1);
  });
});
