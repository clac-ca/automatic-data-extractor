import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import {
  Group as ResizablePanelGroup,
  Panel as ResizablePanel,
  Separator as ResizableHandle,
} from "react-resizable-panels";
import type { GroupImperativeHandle, PanelSize } from "react-resizable-panels";

type Orientation = "horizontal" | "vertical";

const PREVIEW_DEFAULT_SIZE = 40;
const COMMENTS_DEFAULT_SIZE = 30;
const TABLE_PANEL_ID = "documents-table-panel";
const PREVIEW_PANEL_ID = "documents-preview-panel";
const MAIN_PANEL_ID = "documents-main-panel";
const COMMENTS_PANEL_ID = "documents-comments-panel";

function ResizeHandle({
  orientation,
  onResizeStart,
}: {
  orientation: Orientation;
  onResizeStart?: () => void;
}) {
  const isVertical = orientation === "vertical";
  return (
    <ResizableHandle
      onPointerDown={onResizeStart}
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
  const verticalGroupRef = useRef<GroupImperativeHandle | null>(null);
  const horizontalGroupRef = useRef<GroupImperativeHandle | null>(null);
  const previewSizeRef = useRef(PREVIEW_DEFAULT_SIZE);
  const commentsSizeRef = useRef(COMMENTS_DEFAULT_SIZE);
  const isUserResizingRef = useRef(false);

  useEffect(() => {
    const handlePointerUp = () => {
      isUserResizingRef.current = false;
    };
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, []);

  useEffect(() => {
    let frame = 0;
    const applyLayout = () => {
      const group = verticalGroupRef.current;
      if (!group) {
        frame = requestAnimationFrame(applyLayout);
        return;
      }
      if (showPreview) {
        const previewSize = previewSizeRef.current;
        const tableSize = Math.max(0, 100 - previewSize);
        group.setLayout({
          [TABLE_PANEL_ID]: tableSize,
          [PREVIEW_PANEL_ID]: previewSize,
        });
        return;
      }
      group.setLayout({
        [TABLE_PANEL_ID]: 100,
        [PREVIEW_PANEL_ID]: 0,
      });
    };
    applyLayout();
    return () => cancelAnimationFrame(frame);
  }, [showPreview]);

  useEffect(() => {
    let frame = 0;
    const applyLayout = () => {
      const group = horizontalGroupRef.current;
      if (!group) {
        frame = requestAnimationFrame(applyLayout);
        return;
      }
      if (showComments) {
        const commentsSize = commentsSizeRef.current;
        const mainSize = Math.max(0, 100 - commentsSize);
        group.setLayout({
          [MAIN_PANEL_ID]: mainSize,
          [COMMENTS_PANEL_ID]: commentsSize,
        });
        return;
      }
      group.setLayout({
        [MAIN_PANEL_ID]: 100,
        [COMMENTS_PANEL_ID]: 0,
      });
    };
    applyLayout();
    return () => cancelAnimationFrame(frame);
  }, [showComments]);

  const handlePreviewResize = (panelSize: PanelSize) => {
    if (!showPreview || !isUserResizingRef.current) return;
    if (panelSize.asPercentage <= 0) return;
    previewSizeRef.current = panelSize.asPercentage;
  };

  const handleCommentsResize = (panelSize: PanelSize) => {
    if (!showComments || !isUserResizingRef.current) return;
    if (panelSize.asPercentage <= 0) return;
    commentsSizeRef.current = panelSize.asPercentage;
  };

  const handleResizeStart = () => {
    isUserResizingRef.current = true;
  };

  return (
    <ResizablePanelGroup
      orientation="horizontal"
      groupRef={horizontalGroupRef}
      defaultLayout={{
        [MAIN_PANEL_ID]: showComments ? 100 - COMMENTS_DEFAULT_SIZE : 100,
        [COMMENTS_PANEL_ID]: showComments ? COMMENTS_DEFAULT_SIZE : 0,
      }}
      className="min-h-0 min-w-0 flex-1 overflow-hidden"
    >
      <ResizablePanel
        id={MAIN_PANEL_ID}
        defaultSize={70}
        minSize={45}
        className="flex min-h-0 min-w-0 flex-col overflow-hidden"
      >
        <ResizablePanelGroup
          orientation="vertical"
          groupRef={verticalGroupRef}
          defaultLayout={{
            [TABLE_PANEL_ID]: showPreview ? 100 - PREVIEW_DEFAULT_SIZE : 100,
            [PREVIEW_PANEL_ID]: showPreview ? PREVIEW_DEFAULT_SIZE : 0,
          }}
          className="h-full min-h-0 min-w-0 overflow-hidden"
        >
          <ResizablePanel
            id={TABLE_PANEL_ID}
            defaultSize={60}
            minSize={35}
            className="flex min-h-0 min-w-0 flex-col overflow-hidden"
          >
            {table}
          </ResizablePanel>
          {showPreview ? (
            <ResizeHandle orientation="vertical" onResizeStart={handleResizeStart} />
          ) : null}
          <ResizablePanel
            id={PREVIEW_PANEL_ID}
            defaultSize={PREVIEW_DEFAULT_SIZE}
            minSize={20}
            collapsible
            collapsedSize={0}
            onResize={handlePreviewResize}
            className="flex min-h-0 min-w-0 flex-col overflow-hidden"
          >
            <div
              className="documents-panel-content"
              data-pane="preview"
              data-state={showPreview ? "open" : "closed"}
              aria-hidden={!showPreview}
            >
              {showPreview ? preview : null}
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </ResizablePanel>
      {showComments ? (
        <ResizeHandle orientation="horizontal" onResizeStart={handleResizeStart} />
      ) : null}
      <ResizablePanel
        id={COMMENTS_PANEL_ID}
        defaultSize={COMMENTS_DEFAULT_SIZE}
        minSize={20}
        collapsible
        collapsedSize={0}
        onResize={handleCommentsResize}
        className="flex min-h-0 min-w-0 flex-col overflow-hidden"
      >
        <div
          className="documents-panel-content"
          data-pane="comments"
          data-state={showComments ? "open" : "closed"}
          aria-hidden={!showComments}
        >
          {showComments ? comments : null}
        </div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
