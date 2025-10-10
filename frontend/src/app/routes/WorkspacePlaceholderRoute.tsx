import { Link } from "react-router-dom";

const SECTIONS: Record<
  string,
  { title: string; description: string; cta?: { href: string; label: string } }
> = {
  overview: {
    title: "Workspace overview",
    description:
      "We’re building dashboards for workspace health, recent activity, and quick links to the actions you use every day.",
  },
  documents: {
    title: "Documents",
    description:
      "Soon you’ll be able to upload spreadsheets or PDFs, monitor extraction progress, and collaborate with teammates in real time.",
    cta: { href: "../overview", label: "Return to overview" },
  },
  jobs: {
    title: "Jobs",
    description:
      "Track the extraction queue, investigate failures, and replay runs. This screen will arrive as we wire the new job service.",
    cta: { href: "../documents", label: "View documents" },
  },
  configurations: {
    title: "Configurations",
    description:
      "Define document types, map columns, and manage deployment snapshots. We’re finalising the design for this configuration hub.",
    cta: { href: "../overview", label: "Back to overview" },
  },
  members: {
    title: "Members",
    description:
      "Invite teammates, review role assignments, and audit workspace permissions. This collaborative surface is up next on the roadmap.",
    cta: { href: "../settings", label: "Workspace settings" },
  },
  settings: {
    title: "Settings",
    description:
      "Adjust workspace preferences, integrations, and retention rules. We’ll expose the full settings experience after the authentication revamp ships.",
  },
};

interface WorkspacePlaceholderRouteProps {
  readonly section: string;
}

export function WorkspacePlaceholderRoute({ section }: WorkspacePlaceholderRouteProps) {
  const entry = SECTIONS[section] ?? {
    title: "Workspace surface coming soon",
    description:
      "We haven’t wired this route yet. Once the backend API is stable we’ll light up the UI here.",
    cta: { href: "/workspaces", label: "View all workspaces" },
  };

  return (
    <div className="space-y-4 text-sm text-slate-600">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-slate-900">{entry.title}</h2>
        <p className="leading-relaxed">{entry.description}</p>
      </div>
      {entry.cta ? (
        <Link
          to={entry.cta.href}
          className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold text-slate-700 transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        >
          {entry.cta.label}
        </Link>
      ) : null}
    </div>
  );
}
