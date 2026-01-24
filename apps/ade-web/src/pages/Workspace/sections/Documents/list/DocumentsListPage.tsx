import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useSession } from "@/providers/auth/SessionContext";
import { useNotifications } from "@/providers/notifications";
import { Button } from "@/components/ui/button";
import { UploadIcon } from "@/components/icons";
import { useConfigurationsQuery } from "@/pages/Workspace/hooks/configurations";
import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";

import {
  useUploadManager,
  type UploadManagerQueueItem,
} from "@/pages/Workspace/sections/Documents/list/upload/useUploadManager";
import { UploadManager } from "@/pages/Workspace/sections/Documents/list/upload/UploadManager";
import { UploadPreflightDialog } from "@/pages/Workspace/sections/Documents/list/upload/UploadPreflightDialog";
import { DocumentsTableView } from "@/pages/Workspace/sections/Documents/list/table/DocumentsTableView";

import "../documents.css";

const XLSX_ACCEPT = ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function isXlsxFile(file: File) {
  return file.name.toLowerCase().endsWith(".xlsx");
}

export default function DocumentsListPage() {
  const session = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const { workspace } = useWorkspaceContext();
  const { notifyToast } = useNotifications();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadPreflightFiles, setUploadPreflightFiles] = useState<File[]>([]);

  const uploadManager = useUploadManager({
    workspaceId: workspace.id,
    concurrency: 10,
  });
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
  const uploadIntent = (location.state as { openUpload?: boolean } | null)?.openUpload ?? false;

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(event.target.files ?? []);
      const accepted = selected.filter(isXlsxFile);
      const rejected = selected.filter((file) => !isXlsxFile(file));

      if (rejected.length > 0) {
        const skippedLabel =
          rejected.length === 1
            ? `Skipped ${rejected[0].name}.`
            : `Skipped ${rejected.length} files.`;

        notifyToast({
          title: "Only .xlsx files are supported.",
          description: skippedLabel,
          intent: "warning",
          duration: 6000,
        });
      }

      if (accepted.length > 0) {
        setUploadPreflightFiles(accepted);
      }
      event.target.value = "";
    },
    [notifyToast],
  );

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

  useEffect(() => {
    if (!uploadIntent) return;
    handleUploadClick();
    navigate(
      {
        pathname: location.pathname,
        search: location.search,
        hash: location.hash,
      },
      { replace: true, state: null },
    );
  }, [
    handleUploadClick,
    location.hash,
    location.pathname,
    location.search,
    navigate,
    uploadIntent,
  ]);

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
        accept={XLSX_ACCEPT}
        multiple
        className="hidden"
        onChange={handleFileInputChange}
      />
    </>
  );

  return (
    <div className="documents flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-background text-foreground">
      <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden py-4">
        <DocumentsTableView
          workspaceId={workspace.id}
          currentUser={currentUser}
          configMissing={configMissing}
          processingPaused={processingPaused}
          toolbarActions={toolbarActions}
          uploadItems={uploadManager.items}
        />
      </section>
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
