import type { AuthProvider } from "../../../shared/api/types";

interface ProviderTileProps {
  provider: AuthProvider;
}

export function ProviderTile({ provider }: ProviderTileProps) {
  return (
    <a
      href={provider.start_url}
      className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-3 text-left text-slate-100 transition hover:border-sky-500 hover:bg-slate-900"
    >
      {provider.icon_url && (
        <img src={provider.icon_url} alt="" className="h-6 w-6" />
      )}
      <span className="text-sm font-medium">Continue with {provider.label}</span>
    </a>
  );
}
