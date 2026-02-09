import { Fragment, useRef } from "react";
import { Ellipsis } from "lucide-react";
import { flexRender, type Row } from "@tanstack/react-table";

import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import {
  getRowPointerIntent,
  shouldActivateRowFromClick,
  shouldActivateRowFromKeyboard,
  type RowPointerIntent,
} from "@/components/data-table/rowInteraction";
import type { DocumentPresenceEntry } from "@/pages/Workspace/hooks/presence/presenceParticipants";

import type { DocumentRow } from "../../shared/types";
import { DocumentPresenceBadges } from "../../shared/presence/DocumentPresenceBadges";
import type { ContextMenuItem } from "@/components/ui/context-menu-simple";

function findCell(row: Row<DocumentRow>, columnId: string) {
  return row.getAllCells().find((cell) => cell.column.id === columnId) ?? null;
}

export function DocumentsMobileCard({
  row,
  presenceEntries,
  actions,
  onActivate,
}: {
  row: Row<DocumentRow>;
  presenceEntries: DocumentPresenceEntry[];
  actions: ContextMenuItem[];
  onActivate?: (document: DocumentRow) => void;
}) {
  const pointerIntentRef = useRef<RowPointerIntent | null>(null);
  const assigneeCell = findCell(row, "assigneeId");
  const tagsCell = findCell(row, "tags");
  const statusCell = findCell(row, "lastRunPhase");
  const updatedCell = findCell(row, "updatedAt");

  return (
    <div
      className="documents-mobile-card"
      tabIndex={0}
      role="button"
      onPointerDownCapture={(event) => {
        pointerIntentRef.current = getRowPointerIntent(event);
      }}
      onClick={(event) => {
        if (!onActivate) return;
        if (!shouldActivateRowFromClick(event, pointerIntentRef.current)) return;
        onActivate(row.original);
      }}
      onKeyDown={(event) => {
        if (!onActivate) return;
        if (!shouldActivateRowFromKeyboard(event)) return;
        event.preventDefault();
        onActivate(row.original);
      }}
    >
      <div className="documents-mobile-card__header">
        <div className="flex min-w-0 flex-1 items-start gap-2">
          <div data-row-interactive className="pt-0.5">
            <Checkbox
              checked={row.getIsSelected()}
              onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
              aria-label={`Select ${row.original.name}`}
            />
          </div>
          <div className="min-w-0 flex-1">
            <div className="documents-mobile-card__title" title={row.original.name}>
              {row.original.name}
            </div>
            <DocumentPresenceBadges
              entries={presenceEntries}
              className="mt-1"
            />
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              data-row-interactive
              aria-label="Open document actions"
            >
              <Ellipsis className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56" data-row-interactive>
            {actions.map((action) => (
              <Fragment key={action.id}>
                {action.dividerAbove ? <DropdownMenuSeparator /> : null}
                <DropdownMenuItem
                  disabled={action.disabled}
                  variant={action.danger ? "destructive" : "default"}
                  onSelect={(event) => {
                    event.preventDefault();
                    action.onSelect();
                  }}
                >
                  {action.icon ? <span className="mr-2 inline-flex items-center">{action.icon}</span> : null}
                  <span className="truncate">{action.label}</span>
                </DropdownMenuItem>
              </Fragment>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="documents-mobile-card__meta-grid">
        <div className="documents-mobile-card__field">
          <div className="documents-mobile-card__label">Assignee</div>
          <div data-row-interactive>
            {assigneeCell ? flexRender(assigneeCell.column.columnDef.cell, assigneeCell.getContext()) : null}
          </div>
        </div>
        <div className="documents-mobile-card__field">
          <div className="documents-mobile-card__label">Tags</div>
          <div data-row-interactive>
            {tagsCell ? flexRender(tagsCell.column.columnDef.cell, tagsCell.getContext()) : null}
          </div>
        </div>
        <div className="documents-mobile-card__field">
          <div className="documents-mobile-card__label">Run status</div>
          {statusCell ? flexRender(statusCell.column.columnDef.cell, statusCell.getContext()) : null}
        </div>
        <div className="documents-mobile-card__field">
          <div className="documents-mobile-card__label">Updated</div>
          {updatedCell ? flexRender(updatedCell.column.columnDef.cell, updatedCell.getContext()) : null}
        </div>
      </div>
    </div>
  );
}
