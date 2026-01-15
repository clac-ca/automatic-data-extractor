import type { ReactNode } from "react";

import {
  Group as ResizablePanelGroup,
  Panel as ResizablePanel,
  Separator as ResizableHandle,
} from "react-resizable-panels";

type Orientation = "horizontal" | "vertical";

function ResizeHandle({ orientation }: { orientation: Orientation }) {
  const isVertical = orientation === "vertical";
  return (
    <ResizableHandle
      className={
        isVertical
          ? "flex h-4 w-full cursor-row-resize items-center justify-center bg-muted/60"
          : "flex h-full w-4 cursor-col-resize items-center justify-center bg-muted/60"
      }
    >
      <div
        className={
          isVertical
            ? "h-1 w-10 rounded-full bg-muted-foreground/50"
            : "h-10 w-1 rounded-full bg-muted-foreground/50"
        }
      />
    </ResizableHandle>
  );
}

export function DocumentsSplitLayout({
  table,
  preview,
  comments,
  showPreview,
  showComments,
}: {
  table: ReactNode;
  preview: ReactNode;
  comments: ReactNode;
  showPreview: boolean;
  showComments: boolean;
}) {
  if (!showPreview && !showComments) {
    return <div className="flex min-h-0 min-w-0 flex-1 flex-col">{table}</div>;
  }

  if (showComments) {
    return (
      <ResizablePanelGroup
        orientation="horizontal"
        className="min-h-0 min-w-0 flex-1"
      >
        <ResizablePanel defaultSize={70} minSize={45} className="min-h-0 min-w-0">
          {showPreview ? (
            <ResizablePanelGroup
              orientation="vertical"
              className="min-h-0 min-w-0 h-full"
            >
              <ResizablePanel defaultSize={60} minSize={35} className="min-h-0 min-w-0">
                {table}
              </ResizablePanel>
              <ResizeHandle orientation="vertical" />
              <ResizablePanel defaultSize={40} minSize={20} className="min-h-0 min-w-0">
                {preview}
              </ResizablePanel>
            </ResizablePanelGroup>
          ) : (
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">{table}</div>
          )}
        </ResizablePanel>
        <ResizeHandle orientation="horizontal" />
        <ResizablePanel defaultSize={30} minSize={20} className="min-h-0 min-w-0">
          {comments}
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  return (
    <ResizablePanelGroup
      orientation="vertical"
      className="min-h-0 min-w-0 flex-1"
    >
      <ResizablePanel defaultSize={60} minSize={35} className="min-h-0 min-w-0">
        {table}
      </ResizablePanel>
      <ResizeHandle orientation="vertical" />
      <ResizablePanel defaultSize={40} minSize={20} className="min-h-0 min-w-0">
        {preview}
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
