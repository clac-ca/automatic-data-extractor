import { useCallback, useMemo, useRef, useState, type ChangeEvent } from "react";

import { useSession } from "@components/providers/auth/SessionContext";
import { useNotifications } from "@components/providers/notifications";
import { Button } from "@components/tablecn/ui/button";
import { UploadIcon } from "@components/icons";
import { useConfigurationsQuery } from "@hooks/configurations";
import { useUploadManager, type UploadManagerQueueItem } from "@hooks/documents/uploadManager";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";

import { UploadManager } from "./components/UploadManager";
import { UploadPreflightDialog } from "./components/UploadPreflightDialog";
import { TablecnDocumentsView } from "./tablecn/components/TablecnDocumentsView";

export default function DocumentsScreen() {
  const session = useSession();
  const { workspace } = useWorkspaceContext();
  const { notifyToast } = useNotifications();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadPreflightFiles, setUploadPreflightFiles] = useState<File[]>([]);

  const uploadManager = useUploadManager({ workspaceId: workspace.id });
  const configurationsQuery = useConfigurationsQuery({ workspaceId: workspace.id });

  const currentUser = useMemo(
    () => ({
      id: session.user.id,
      email: session.user.email,
      label: session.user.display_name || session.user.email || "You",
    }),
    [session.user.display_name, session.user.email, session.user.id],
  );

  const activeConfiguration = useMemo(() => {
    const items = configurationsQuery.data?.items ?? [];
    return items.find((config) => config.status === "active") ?? null;
  }, [configurationsQuery.data?.items]);

  const configMissing = configurationsQuery.isSuccess && !activeConfiguration;
  const processingPaused = workspace.processing_paused ?? false;

  const handleUploadClick = useCallback(() => fileInputRef.current?.click(), []);

  const handleFileInputChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(event.target.files ?? []);
    if (selected.length > 0) {
      setUploadPreflightFiles(selected);
    }
    event.target.value = "";
  }, []);

  const handleUploadConfirm = useCallback(
    (items: UploadManagerQueueItem[]) => {
      if (!items.length) return;
      const nextItems = uploadManager.enqueue(items);

      const description = processingPaused
        ? configMissing
          ? "Uploads saved. Processing is paused and no configuration is active yet."
          : "Uploads saved. Processing is paused for this workspace."
        : configMissing
          ? "Uploads saved. Processing will start once an active configuration is set."
          : "Processing will begin automatically.";

      notifyToast({
        title: `${nextItems.length} file${nextItems.length === 1 ? "" : "s"} added`,
        description,
        intent: "success",
      });

      setUploadPreflightFiles([]);
    },
    [configMissing, notifyToast, processingPaused, uploadManager],
  );

  const handleUploadCancel = useCallback(() => {
    setUploadPreflightFiles([]);
  }, []);

  const toolbarActions = (
    <>
      <UploadManager
        items={uploadManager.items}
        summary={uploadManager.summary}
        onPause={uploadManager.pause}
        onResume={uploadManager.resume}
        onRetry={uploadManager.retry}
        onCancel={uploadManager.cancel}
        onRemove={uploadManager.remove}
        onClearCompleted={uploadManager.clearCompleted}
      />
      <Button size="sm" onClick={handleUploadClick} className="gap-2">
        <UploadIcon className="h-4 w-4" />
        Upload
      </Button>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleFileInputChange}
      />
    </>
  );

  return (
    <div className="documents flex min-h-0 flex-1 flex-col bg-background text-foreground">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-6 py-4">
          <TablecnDocumentsView
            workspaceId={workspace.id}
            currentUser={currentUser}
            toolbarActions={toolbarActions}
          />
        </section>
      </div>
      <UploadPreflightDialog
        open={uploadPreflightFiles.length > 0}
        files={uploadPreflightFiles}
        onConfirm={handleUploadConfirm}
        onCancel={handleUploadCancel}
        processingPaused={processingPaused}
        configMissing={configMissing}
      />
    </div>
  );
}
