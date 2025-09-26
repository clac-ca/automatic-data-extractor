import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthProvider } from "./app/auth/AuthContext";
import { WorkspaceSelectionProvider } from "./app/workspaces/WorkspaceSelectionContext";
import { ToastProvider } from "./components/ToastProvider";
import "./App.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <ToastProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <WorkspaceSelectionProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </WorkspaceSelectionProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ToastProvider>
  </React.StrictMode>,
);
