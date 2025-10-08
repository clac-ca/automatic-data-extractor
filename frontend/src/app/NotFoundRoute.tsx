export function NotFoundRoute() {
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-3 px-4 text-center">
      <h1 className="text-2xl font-semibold text-slate-50">Page not found</h1>
      <p className="text-sm text-slate-400">The page you were trying to view does not exist.</p>
      <a href="/" className="text-sm font-medium text-sky-300 hover:text-sky-200">
        Go back home
      </a>
    </div>
  );
}
