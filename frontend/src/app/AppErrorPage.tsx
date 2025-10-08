import { Link, useRouteError } from "react-router-dom";

export function AppErrorPage() {
  const error = useRouteError() as { statusText?: string; message?: string } | undefined;
  const message = error?.statusText || error?.message || "Something went wrong.";

  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-semibold text-slate-50">Unable to load ADE</h1>
      <p className="text-sm text-slate-400">{message}</p>
      <Link to="/" className="text-sm font-medium text-sky-300 hover:text-sky-200">
        Return to start
      </Link>
    </div>
  );
}
