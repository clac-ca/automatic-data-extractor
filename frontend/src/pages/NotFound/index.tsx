import { Link } from "react-router-dom";

export default function NotFoundScreen() {
  return (
    <div className="mx-auto flex min-h-full max-w-xl flex-col justify-center px-6 py-16 text-center">
      <div className="space-y-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          404
        </p>
        <h1 className="text-3xl font-semibold text-foreground">Page not found</h1>
        <p className="text-sm text-muted-foreground">
          The resource you&apos;re looking for doesn&apos;t exist yet. Add a page under <code>src/pages/&lt;PageName&gt;/</code> and
          register it inside <code>src/app/routes.tsx</code> if this surface should exist in the app.
        </p>
        <div className="flex justify-center gap-3 text-sm">
          <Link
            to="/"
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Return home
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center rounded-lg border border-border bg-card px-4 py-2 font-semibold text-muted-foreground transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Go to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
