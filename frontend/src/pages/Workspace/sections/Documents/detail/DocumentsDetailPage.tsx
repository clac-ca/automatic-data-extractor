import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceDocumentRowById } from "@/api/documents";
import { ApiError } from "@/api/errors";
import { PageState } from "@/components/layout";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
import type { DocumentDetailTab } from "@/pages/Workspace/sections/Documents/shared/navigation";
import { useNotifications } from "@/providers/notifications";

import { DocumentTicketHeader } from "./components/DocumentTicketHeader";
import { useDocumentDetailUrlState } from "./hooks/useDocumentDetailUrlState";
import { DocumentActivityTab } from "./tabs/activity/DocumentActivityTab";
import { DocumentPreviewTab } from "./tabs/preview/DocumentPreviewTab";
import { getRenameDocumentErrorMessage, useRenameDocumentMutation } from "../shared/hooks/useRenameDocumentMutation";
import { RenameDocumentDialog } from "../shared/ui/RenameDocumentDialog";

export function DocumentsDetailPage({ documentId }: { documentId: string }) {
  const navigate = useNavigate();
  const { workspace } = useWorkspaceContext();
  const { sendSelection } = useWorkspacePresence();
  const { notifyToast } = useNotifications();
  const renameMutation = useRenameDocumentMutation({ workspaceId: workspace.id });
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);

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
  });

  const documentRow = documentQuery.data ?? null;

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
    </div>
  );
}
