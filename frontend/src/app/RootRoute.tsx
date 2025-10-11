import { Navigate, useLoaderData } from "react-router-dom";

import { resolveSessionDestination } from "../features/auth/utils/resolveSessionDestination";
import type { RootLoaderData } from "./loaders/rootLoader";

export function RootRoute() {
  const { session, setupStatus, setupError } = useLoaderData() as RootLoaderData;

  if (setupError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-center text-sm text-rose-200">
        <p>We were unable to determine the application setup state.</p>
        <a href="/" className="font-medium text-sky-300 hover:text-sky-200">
          Try again
        </a>
      </div>
    );
  }

  if (setupStatus?.requires_setup) {
    return <Navigate to="/setup" replace />;
  }

  if (session) {
    return <Navigate to={resolveSessionDestination(session)} replace />;
  }

  return <Navigate to="/login" replace />;
}
