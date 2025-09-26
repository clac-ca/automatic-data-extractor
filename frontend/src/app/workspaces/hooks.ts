import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";

import { fetchWorkspaceContext, fetchWorkspaces } from "../../api/workspaces";
import {
  isUnauthorizedError,
  normaliseErrorMessage,
} from "../../api/errors";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../../components/ToastProvider";

const WORKSPACES_QUERY_KEY = ["workspaces"] as const;

function workspaceContextKey(workspaceId: string | null) {
  return workspaceId ? (["workspace", workspaceId] as const) : ["workspace"];
}

export function useWorkspacesQuery() {
  const auth = useAuth();
  const { pushToast } = useToast();
  const lastError = useRef<unknown>(null);

  const query = useQuery({
    queryKey: WORKSPACES_QUERY_KEY,
    enabled: auth.status === "authenticated" && Boolean(auth.token),
    queryFn: async () => {
      if (!auth.token) {
        throw new Error("Authentication required");
      }
      return fetchWorkspaces(auth.token);
    },
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const { error } = query;

  useEffect(() => {
    if (!error) {
      lastError.current = null;
      return;
    }
    if (lastError.current === error) {
      return;
    }
    lastError.current = error;
    if (isUnauthorizedError(error)) {
      pushToast({
        tone: "error",
        title: "Session expired",
        description: "Please sign in again to continue.",
      });
      auth.signOut();
      return;
    }
    pushToast({
      tone: "error",
      title: "Workspace error",
      description: normaliseErrorMessage(error),
    });
  }, [auth, error, pushToast]);

  return query;
}

export function useWorkspaceContextQuery(workspaceId: string | null) {
  const auth = useAuth();
  const { pushToast } = useToast();
  const queryClient = useQueryClient();
  const lastError = useRef<unknown>(null);

  const queryKey = useMemo(() => workspaceContextKey(workspaceId), [workspaceId]);

  const query = useQuery({
    queryKey,
    enabled:
      Boolean(workspaceId) && auth.status === "authenticated" && Boolean(auth.token),
    queryFn: async () => {
      if (!workspaceId) {
        throw new Error("Workspace identifier is required");
      }
      if (!auth.token) {
        throw new Error("Authentication required");
      }
      return fetchWorkspaceContext(auth.token, workspaceId);
    },
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const { error } = query;

  useEffect(() => {
    if (!error) {
      lastError.current = null;
      return;
    }
    if (lastError.current === error) {
      return;
    }
    lastError.current = error;
    if (isUnauthorizedError(error)) {
      pushToast({
        tone: "error",
        title: "Session expired",
        description: "Please sign in again to continue.",
      });
      auth.signOut();
      queryClient.removeQueries({ queryKey });
      return;
    }
    pushToast({
      tone: "error",
      title: "Workspace error",
      description: normaliseErrorMessage(error),
    });
  }, [auth, error, pushToast, queryClient, queryKey]);

  return query;
}
