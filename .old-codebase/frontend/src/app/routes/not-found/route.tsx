import { Link } from "react-router-dom";

export default function NotFoundRoute() {
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6 py-16 text-center">
      <div className="space-y-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">
          404
        </p>
        <h1 className="text-3xl font-semibold text-slate-900">Page not found</h1>
        <p className="text-sm text-slate-600">
          The resource you&apos;re looking for doesn&apos;t exist yet. If this surface should be part of the rebuild, add a route in <code>src/app/routes</code> and connect the relevant feature.
        </p>
        <div className="flex justify-center gap-3 text-sm">
          <Link
            to="/"
            className="focus-ring inline-flex items-center rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white transition hover:bg-brand-700"
          >
            Return home
          </Link>
          <Link
            to="/login"
            className="focus-ring inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold text-slate-600 hover:bg-slate-50"
          >
            Go to sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
