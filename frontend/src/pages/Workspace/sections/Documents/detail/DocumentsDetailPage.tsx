import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceDocumentRowById } from "@/api/documents";
import { ApiError } from "@/api/errors";
import { cancelRun, createRun } from "@/api/runs/api";
import type { RunStreamOptions } from "@/api/runs/api";
import { PageState } from "@/components/layout";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
import type { DocumentDetailTab } from "@/pages/Workspace/sections/Documents/shared/navigation";
import { useNotifications } from "@/providers/notifications";

import { DocumentTicketHeader } from "./components/DocumentTicketHeader";
import { useDocumentDetailUrlState } from "./hooks/useDocumentDetailUrlState";
import { useDocumentDetailLiveSync } from "./hooks/useDocumentDetailLiveSync";
import { DocumentActivityTab } from "./tabs/activity/DocumentActivityTab";
import { DocumentPreviewTab } from "./tabs/preview/DocumentPreviewTab";
import { getRenameDocumentErrorMessage, useRenameDocumentMutation } from "../shared/hooks/useRenameDocumentMutation";
import { RenameDocumentDialog } from "../shared/ui/RenameDocumentDialog";
import { ReprocessPreflightDialog } from "../list/upload/ReprocessPreflightDialog";

export function DocumentsDetailPage({ documentId }: { documentId: string }) {
  const navigate = useNavigate();
  const { workspace } = useWorkspaceContext();
  const { sendSelection } = useWorkspacePresence();
  const { notifyToast } = useNotifications();
  const renameMutation = useRenameDocumentMutation({ workspaceId: workspace.id });
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [reprocessOpen, setReprocessOpen] = useState(false);
  const [isRunActionPending, setIsRunActionPending] = useState(false);

  const {
    state: detailState,
    setTab,
    setActivityFilter,
    setPreviewSource,
    setPreviewSheet,
  } = useDocumentDetailUrlState();

  const documentQuery = useQuery({
    queryKey: ["documents-detail", workspace.id, documentId],
    queryFn: ({ signal }) =>
      fetchWorkspaceDocumentRowById(
        workspace.id,
        documentId,
        {
          includeRunMetrics: true,
          includeRunTableColumns: true,
          includeRunFields: true,
        },
        signal,
      ),
    enabled: Boolean(workspace.id && documentId),
    staleTime: 30_000,
    refetchInterval: (query) => {
      const data = query.state.data;
      const status = data?.lastRun?.status ?? null;
      return status === "queued" || status === "running" ? 1_000 : false;
    },
    refetchIntervalInBackground: true,
  });

  const documentRow = documentQuery.data ?? null;
  const isRunActive = documentRow?.lastRun?.status === "queued" || documentRow?.lastRun?.status === "running";

  useDocumentDetailLiveSync({
    workspaceId: workspace.id,
    documentId,
    enabled: Boolean(workspace.id && documentId),
  });

  useEffect(() => {
    sendSelection({ documentId });
    return () => {
      sendSelection({ documentId: null });
    };
  }, [documentId, sendSelection]);

  const onBack = () => {
    navigate(`/workspaces/${workspace.id}/documents`);
  };

  const onRenameConfirm = useCallback(
    async (nextName: string) => {
      if (!documentRow) return;
      setRenameError(null);
      try {
        const result = await renameMutation.renameDocument({
          documentId: documentRow.id,
          currentName: documentRow.name,
          nextName,
        });
        if (!result) {
          setRenameOpen(false);
          return;
        }
        notifyToast({
          title: "Document renamed.",
          intent: "success",
          duration: 4000,
        });
        setRenameOpen(false);
      } catch (error) {
        const description = getRenameDocumentErrorMessage(error);
        setRenameError(description);
        notifyToast({
          title: "Unable to rename document",
          description,
          intent: "danger",
        });
      }
    },
    [documentRow, notifyToast, renameMutation],
  );

  const onCancelRunRequest = useCallback(async () => {
    if (!documentRow) return;
    const runId = isRunActive ? documentRow.lastRun?.id : null;
    if (!runId) {
      notifyToast({
        title: "Run is no longer active",
        description: "Only queued or running runs can be cancelled.",
        intent: "warning",
      });
      return;
    }

    setIsRunActionPending(true);
    try {
      await cancelRun(workspace.id, runId);
      notifyToast({
        title: "Run cancelled",
        description: `${documentRow.name} was cancelled.`,
        intent: "success",
      });
      await documentQuery.refetch();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        notifyToast({
          title: "Run already finished",
          description: `${documentRow.name} is already in a terminal state.`,
          intent: "warning",
        });
        return;
      }
      notifyToast({
        title: "Unable to cancel run",
        description: error instanceof Error ? error.message : "Please try again.",
        intent: "danger",
      });
    } finally {
      setIsRunActionPending(false);
    }
  }, [documentQuery, documentRow, isRunActive, notifyToast, workspace.id]);

  const onReprocessConfirm = useCallback(
    async (runOptions: Pick<RunStreamOptions, "active_sheet_only" | "input_sheet_names">) => {
      if (!documentRow) return;
      setIsRunActionPending(true);
      try {
        await createRun(workspace.id, {
          input_document_id: documentRow.id,
          active_sheet_only: runOptions.active_sheet_only,
          input_sheet_names: runOptions.input_sheet_names,
        });
        notifyToast({
          title: "Reprocess queued",
          description: `${documentRow.name} was queued for processing.`,
          intent: "success",
        });
        setReprocessOpen(false);
        await documentQuery.refetch();
      } catch (error) {
        notifyToast({
          title: "Unable to reprocess document",
          description: error instanceof Error ? error.message : "Please try again.",
          intent: "danger",
        });
      } finally {
        setIsRunActionPending(false);
      }
    },
    [documentQuery, documentRow, notifyToast, workspace.id],
  );

  if (documentQuery.isLoading) {
    return (
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            Loading…
          </div>
        </div>
      </div>
    );
  }

  if (documentQuery.isError) {
    const error = documentQuery.error;
    const message =
      error instanceof ApiError
        ? error.status === 404
          ? "We couldn’t find that document. It may have been deleted."
          : error.status === 403
            ? "You don’t have access to that document."
            : error.message
        : error instanceof Error
          ? error.message
          : "We couldn’t load that document.";

    return (
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <PageState title="Unable to load document" description={message} variant="error" />
      </div>
    );
  }

  if (!documentRow) {
    return (
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <PageState
          title="Document not available"
          description="We couldn’t load that document."
          variant="error"
        />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background text-foreground">
      <DocumentTicketHeader
        workspaceId={workspace.id}
        document={documentRow}
        onBack={onBack}
        onRenameRequest={() => {
          setRenameError(null);
          setRenameOpen(true);
        }}
        onReprocessRequest={() => setReprocessOpen(true)}
        onCancelRunRequest={onCancelRunRequest}
        isRunActionPending={isRunActionPending}
      />

      <TabsRoot value={detailState.tab} onValueChange={(value) => setTab(value as DocumentDetailTab)}>
        <TabsList className="flex gap-1 border-b bg-background px-4 py-2">
          <TabsTrigger
            value="activity"
            className={[
              "rounded-md px-3 py-1.5 text-sm",
              detailState.tab === "activity"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            Activity
          </TabsTrigger>
          <TabsTrigger
            value="preview"
            className={[
              "rounded-md px-3 py-1.5 text-sm",
              detailState.tab === "preview"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            Preview
          </TabsTrigger>
        </TabsList>

        <div className="min-h-0 flex-1 overflow-hidden">
          <TabsContent value="activity" className="min-h-0 flex h-full flex-col">
            <DocumentActivityTab
              workspaceId={workspace.id}
              document={documentRow}
              filter={detailState.activityFilter}
              onFilterChange={setActivityFilter}
            />
          </TabsContent>
          <TabsContent value="preview" className="min-h-0 flex h-full flex-col">
            <DocumentPreviewTab
              workspaceId={workspace.id}
              document={documentRow}
              source={detailState.source}
              sheet={detailState.sheet}
              onSourceChange={setPreviewSource}
              onSheetChange={setPreviewSheet}
            />
          </TabsContent>
        </div>
      </TabsRoot>
      <RenameDocumentDialog
        open={renameOpen}
        documentName={documentRow.name}
        isPending={renameMutation.isRenaming}
        errorMessage={renameError}
        onOpenChange={(open) => {
          setRenameOpen(open);
          if (!open) {
            setRenameError(null);
            renameMutation.reset();
          }
        }}
        onClearError={() => {
          if (renameError) setRenameError(null);
        }}
        onSubmit={onRenameConfirm}
      />
      <ReprocessPreflightDialog
        open={reprocessOpen}
        workspaceId={workspace.id}
        documents={[
          {
            id: documentRow.id,
            name: documentRow.name,
            fileType: documentRow.fileType,
          },
        ]}
        onConfirm={onReprocessConfirm}
        onCancel={() => {
          if (isRunActionPending) return;
          setReprocessOpen(false);
        }}
        processingPaused={workspace.processing_paused}
        configMissing={false}
        isSubmitting={isRunActionPending}
      />
    </div>
  );
}
