import { useEffect, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useWorkspaceContext } from "@/pages/Workspace/context/WorkspaceContext";

export function WorkspaceDocumentsStreamProvider({ children }: { readonly children: ReactNode }) {
  const { workspace } = useWorkspaceContext();
  const queryClient = useQueryClient();

  const invalidateWorkspaceDocuments = () => {
    if (!workspace.id) return;
    queryClient.invalidateQueries({ queryKey: ["documents", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["sidebar", "assigned-documents", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["documents-preview-row", workspace.id] });
    queryClient.invalidateQueries({ queryKey: ["documents-preview-details", workspace.id] });
  };

  useEffect(() => {
    if (!workspace.id) return;
    const handleFocus = () => invalidateWorkspaceDocuments();
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        invalidateWorkspaceDocuments();
      }
    };
    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [queryClient, workspace.id]);

  return <>{children}</>;
}
