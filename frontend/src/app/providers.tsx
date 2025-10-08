import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

interface AppProvidersProps {
  children: ReactNode;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry(failureCount, error) {
        if (error instanceof Error && "status" in error && (error as { status: number }).status === 401) {
          return false;
        }

        return failureCount < 2;
      },
    },
  },
});

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
