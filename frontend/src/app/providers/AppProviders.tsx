import { type ReactNode, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { SessionProvider } from "@app/providers/SessionProvider";
import { StatusProvider } from "@app/providers/StatusProvider";
import { ToastProvider } from "@app/providers/ToastProvider";
import { WorkspaceProvider } from "@app/providers/WorkspaceProvider";

interface AppProvidersProps {
  readonly children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps): JSX.Element {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: 1,
            staleTime: 30_000
          }
        }
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <WorkspaceProvider>
          <StatusProvider>
            <ToastProvider>{children}</ToastProvider>
          </StatusProvider>
        </WorkspaceProvider>
      </SessionProvider>
    </QueryClientProvider>
  );
}
