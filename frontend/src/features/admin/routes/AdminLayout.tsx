import { NavLink, Outlet, useLocation } from "react-router-dom";

const tabs = [
  { to: "/admin/global/roles", label: "Global roles" },
  { to: "/admin/global/assignments", label: "Global assignments" },
  { to: "/admin/workspace", label: "Workspace assignments" },
];

export function AdminLayout() {
  const location = useLocation();

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-100">Administration</h1>
        <p className="text-sm text-slate-300">
          Manage global roles, workspace role assignments, and administrator access across ADE.
        </p>
      </header>
      <nav aria-label="Administration sections" className="flex flex-wrap gap-2">
        {tabs.map((tab) => {
          const isActive = location.pathname.startsWith(tab.to);
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive: match }) =>
                `rounded px-3 py-2 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-950 ${
                  match || isActive
                    ? "bg-sky-500 text-slate-950"
                    : "bg-slate-900 text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              {tab.label}
            </NavLink>
          );
        })}
      </nav>
      <section className="rounded border border-slate-800 bg-slate-950/60 p-6">
        <Outlet />
      </section>
    </div>
  );
}
