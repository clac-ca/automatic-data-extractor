export function RunInputCell({ name, id }: { name: string; id: string }) {
  return (
    <div className="min-w-0">
      <p className="truncate font-semibold text-foreground">{name}</p>
      <p className="truncate text-[11px] text-muted-foreground">{id}</p>
    </div>
  );
}
