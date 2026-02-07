import { useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchWorkspaceDocumentRowById } from "@/api/documents";
import { ApiError } from "@/api/errors";
import { PageState } from "@/components/layout";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";
import {
  getDocumentDetailState,
  normalizeLegacyDocumentDetailSearch,
  type DocumentActivityFilter,
  type DocumentDetailTab,
  type DocumentPreviewSource,
} from "@/pages/Workspace/sections/Documents/shared/navigation";

import { DocumentTicketHeader } from "./components/DocumentTicketHeader";
import { DocumentActivityTab } from "./tabs/activity/DocumentActivityTab";
import { DocumentPreviewTab } from "./tabs/preview/DocumentPreviewTab";

export function DocumentsDetailPage({ documentId }: { documentId: string }) {
  const navigate = useNavigate();
  const { workspace } = useWorkspaceContext();
  const { sendSelection } = useWorkspacePresence();
  const [searchParams, setSearchParams] = useSearchParams();
  const detailState = useMemo(
    () => getDocumentDetailState(searchParams),
    [searchParams],
  );

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

  useEffect(() => {
    const normalized = normalizeLegacyDocumentDetailSearch(searchParams);
    if (!normalized) return;
    setSearchParams(normalized, { replace: true });
  }, [searchParams, setSearchParams]);

  const onBack = () => {
    navigate(`/workspaces/${workspace.id}/documents`);
  };

  const onTabChange = (nextValue: DocumentDetailTab) => {
    const params = new URLSearchParams(searchParams);
    params.set("tab", nextValue);
    if (nextValue === "preview") {
      params.delete("activityFilter");
    }
    setSearchParams(params, { replace: true });
  };

  const onActivityFilterChange = (nextFilter: DocumentActivityFilter) => {
    const params = new URLSearchParams(searchParams);
    params.set("tab", "activity");
    if (nextFilter === "all") {
      params.delete("activityFilter");
    } else {
      params.set("activityFilter", nextFilter);
    }
    setSearchParams(params, { replace: true });
  };

  const onPreviewSourceChange = (nextSource: DocumentPreviewSource) => {
    const params = new URLSearchParams(searchParams);
    params.set("tab", "preview");
    params.delete("activityFilter");
    params.set("source", nextSource);
    setSearchParams(params, { replace: true });
  };

  const onPreviewSheetChange = (nextSheet: string | null) => {
    const params = new URLSearchParams(searchParams);
    if (!nextSheet) {
      params.delete("sheet");
    } else {
      params.set("sheet", nextSheet);
    }
    setSearchParams(params, { replace: true });
  };

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
      />

      <TabsRoot
        value={detailState.tab}
        onValueChange={(value) => onTabChange(value as DocumentDetailTab)}
      >
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
              onFilterChange={onActivityFilterChange}
            />
          </TabsContent>
          <TabsContent value="preview" className="min-h-0 flex h-full flex-col">
            <DocumentPreviewTab
              workspaceId={workspace.id}
              document={documentRow}
              source={detailState.source}
              sheet={detailState.sheet}
              onSourceChange={onPreviewSourceChange}
              onSheetChange={onPreviewSheetChange}
            />
          </TabsContent>
        </div>
      </TabsRoot>
    </div>
  );
}
