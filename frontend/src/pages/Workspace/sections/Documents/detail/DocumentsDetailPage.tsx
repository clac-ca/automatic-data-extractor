import { useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";

import { fetchWorkspaceDocumentRowById } from "@/api/documents";
import { ApiError } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { PageState } from "@/components/layout";
import { TabsContent, TabsList, TabsRoot, TabsTrigger } from "@/components/ui/tabs";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";
import { useWorkspacePresence } from "@/pages/Workspace/context/WorkspacePresenceContext";

import { DocumentsCommentsPanel } from "./tabs/comments/components/DocumentsCommentsPanel";
import { DocumentsPreviewContent } from "./tabs/data/components/DocumentsPreviewContent";
import { DocumentsTimelinePanel } from "./tabs/timeline/components/DocumentsTimelinePanel";

export function DocumentsDetailPage({ documentId }: { documentId: string }) {
  const navigate = useNavigate();
  const { workspace } = useWorkspaceContext();
  const { sendSelection } = useWorkspacePresence();
  const [searchParams, setSearchParams] = useSearchParams();

  const tab = (searchParams.get("tab") ?? "data") as "data" | "comments" | "timeline";
  const activeTab = tab === "comments" || tab === "timeline" ? tab : "data";

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

  const headerSubtitle = useMemo(() => {
    if (!documentRow?.lastRun?.status) return null;
    const normalized = String(documentRow.lastRun.status).replace(/_/g, " ");
    return `Last run: ${normalized[0]?.toUpperCase() ?? ""}${normalized.slice(1)}`;
  }, [documentRow?.lastRun?.status]);

  const onBack = () => {
    navigate(`/workspaces/${workspace.id}/documents`);
  };

  const onTabChange = (nextValue: string) => {
    const params = new URLSearchParams(searchParams);
    if (nextValue === "comments" || nextValue === "timeline") {
      params.set("tab", nextValue);
    } else {
      params.delete("tab");
    }
    setSearchParams(params, { replace: true });
  };

  if (documentQuery.isLoading) {
    return (
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b bg-background px-4 py-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="gap-1">
            <ChevronLeft className="h-4 w-4" />
            Back
          </Button>
          <div className="text-sm text-muted-foreground">Loading document…</div>
        </div>
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
      <div className="flex items-center gap-3 border-b bg-background px-4 py-3">
        <Button variant="ghost" size="sm" onClick={onBack} className="gap-1">
          <ChevronLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold" title={documentRow.name}>
            {documentRow.name}
          </div>
          {headerSubtitle ? (
            <div className="text-xs text-muted-foreground">{headerSubtitle}</div>
          ) : null}
        </div>
      </div>

      <TabsRoot value={activeTab} onValueChange={onTabChange}>
        <TabsList className="flex gap-1 border-b bg-background px-4 py-2">
          <TabsTrigger
            value="data"
            className={[
              "rounded-md px-3 py-1.5 text-sm",
              activeTab === "data"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            Data
          </TabsTrigger>
          <TabsTrigger
            value="comments"
            className={[
              "rounded-md px-3 py-1.5 text-sm",
              activeTab === "comments"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            Comments
          </TabsTrigger>
          <TabsTrigger
            value="timeline"
            className={[
              "rounded-md px-3 py-1.5 text-sm",
              activeTab === "timeline"
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            Timeline
          </TabsTrigger>
        </TabsList>

        <div className="min-h-0 flex-1 overflow-hidden">
          <TabsContent value="data" className="min-h-0 flex h-full flex-col">
            <DocumentsPreviewContent workspaceId={workspace.id} document={documentRow} />
          </TabsContent>
          <TabsContent value="comments" className="min-h-0 flex h-full flex-col">
            <DocumentsCommentsPanel workspaceId={workspace.id} document={documentRow} />
          </TabsContent>
          <TabsContent value="timeline" className="min-h-0 flex h-full flex-col">
            <DocumentsTimelinePanel workspaceId={workspace.id} document={documentRow} />
          </TabsContent>
        </div>
      </TabsRoot>
    </div>
  );
}
