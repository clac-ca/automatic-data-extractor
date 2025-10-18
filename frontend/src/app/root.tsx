import type { ReactNode } from "react";
import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";

import { AppProviders } from "./AppProviders";
import { NotFound } from "@app/routes/components/NotFound";
import { Button } from "@ui/button";
import { PageState } from "@ui/PageState";

interface LayoutProps {
  readonly children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <html lang="en" className="h-full bg-slate-50">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body className="min-h-full text-slate-900 antialiased">
        <AppProviders>{children}</AppProviders>
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function Root() {
  return <Outlet />;
}

interface ErrorBoundaryProps {
  readonly error: unknown;
}

export function ErrorBoundary({ error }: ErrorBoundaryProps) {
  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <Layout>
        <NotFound />
      </Layout>
    );
  }

  let message: ReactNode = "An unexpected error occurred. Refresh the page or try again.";

  if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === "string") {
    message = error;
  }

  return (
    <Layout>
      <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-16">
        <PageState
          title="Something went wrong"
          description={
            <span className="block max-w-md">
              {message}
              <br />
              If the issue persists, contact an administrator.
            </span>
          }
          variant="error"
          action={
            <Button type="button" variant="secondary" onClick={() => window.location.reload()}>
              Reload page
            </Button>
          }
        />
      </div>
    </Layout>
  );
}
