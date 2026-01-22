---
title: Data Table
description: Server-driven table with URL-synced sorting, filtering, pagination, and selection.
component: true
---

The ADE data table is a TanStack Table wrapper optimized for server-driven lists. It keeps state in the URL via `nuqs`, ships with simple and advanced filter UIs, and includes pagination, column visibility, and row selection helpers.

## Prerequisites

The data table uses `nuqs` for URL state. Ensure the app is wrapped in the `NuqsAdapter` from `nuqs/adapters/react-router/v7`. This is already done in `src/app/layouts/AppShell.tsx`, but if you render a table outside that tree, wrap the root:

```tsx
import { NuqsAdapter } from "nuqs/adapters/react-router/v7";

<NuqsAdapter>
  <App />
</NuqsAdapter>
```

## Quick start

1. Define columns with explicit `id`s and filter metadata.

```tsx
import type { ColumnDef } from "@tanstack/react-table";

import { DataTableColumnHeader } from "@/components/data-table/data-table-column-header";

type Row = {
  id: string;
  name: string;
  status: "active" | "inactive";
  createdAt: string;
};

const columns: ColumnDef<Row>[] = [
  {
    id: "name",
    accessorKey: "name",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} label="Name" />
    ),
    meta: {
      label: "Name",
      placeholder: "Search names...",
      variant: "text",
    },
    enableSorting: true,
    enableColumnFilter: true,
  },
  {
    id: "status",
    accessorKey: "status",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} label="Status" />
    ),
    meta: {
      label: "Status",
      variant: "select",
      options: [
        { label: "Active", value: "active" },
        { label: "Inactive", value: "inactive" },
      ],
    },
    enableSorting: true,
    enableColumnFilter: true,
  },
  {
    id: "createdAt",
    accessorKey: "createdAt",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} label="Created" />
    ),
    enableSorting: true,
  },
];
```

2. Create the table instance with `useDataTable`.

```tsx
import { useDataTable } from "@/hooks/use-data-table";

const { table } = useDataTable({
  data,
  columns,
  pageCount,
  initialState: {
    sorting: [{ id: "createdAt", desc: true }],
    pagination: { pageSize: 20 },
  },
  getRowId: (row) => row.id,
});
```

3. Compose the UI.

```tsx
import { DataTable } from "@/components/data-table/data-table";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";

<DataTable table={table}>
  <DataTableToolbar table={table}>
    <DataTableSortList table={table} align="start" />
  </DataTableToolbar>
</DataTable>
```

## Layout patterns

### Standard toolbar (simple filters)

Use `DataTableToolbar` when you want per-column filters rendered directly in the toolbar based on column `meta.variant`.

```tsx
import { DataTable } from "@/components/data-table/data-table";
import { DataTableToolbar } from "@/components/data-table/data-table-toolbar";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";

<DataTable table={table}>
  <DataTableToolbar table={table}>
    <DataTableSortList table={table} align="start" />
  </DataTableToolbar>
</DataTable>
```

### Advanced toolbar (filter builder)

Use `DataTableAdvancedToolbar` with either `DataTableFilterList` or `DataTableFilterMenu` for multi-operator filters and an AND/OR join operator.

```tsx
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";
import { useDataTable } from "@/hooks/use-data-table";

const { table, debounceMs, throttleMs, shallow } = useDataTable({
  data,
  columns,
  pageCount,
  enableAdvancedFilter: true,
  clearOnDefault: true,
});

<DataTableAdvancedToolbar table={table}>
  <DataTableSortList table={table} align="start" />
  <DataTableFilterList
    table={table}
    align="start"
    debounceMs={debounceMs}
    throttleMs={throttleMs}
    shallow={shallow}
  />
</DataTableAdvancedToolbar>
```

Swap `DataTableFilterList` for `DataTableFilterMenu` if you want a command palette style filter picker.

### Custom layouts

The hook is decoupled from the table UI. You can use `useDataTable` to drive non-table layouts (cards, lists) and still keep pagination, sorting, and filters in sync. `Workspaces` uses this pattern:

```tsx
import { DataTableAdvancedToolbar } from "@/components/data-table/data-table-advanced-toolbar";
import { DataTableFilterList } from "@/components/data-table/data-table-filter-list";
import { DataTablePagination } from "@/components/data-table/data-table-pagination";
import { DataTableSortList } from "@/components/data-table/data-table-sort-list";

<DataTableAdvancedToolbar table={table}>
  <DataTableSortList table={table} align="start" />
  <DataTableFilterList table={table} align="start" />
</DataTableAdvancedToolbar>

{/* custom grid or cards */}

<DataTablePagination table={table} />
```

## Column definitions

`ColumnDef` entries should include explicit `id`s. The URL parsers use those IDs to validate sorting and filter payloads.

### Column meta

`ColumnDef.meta` drives the filter UI. Supported keys:

| meta key | type | description |
| --- | --- | --- |
| `label` | `string` | Display label used in menus and pills. |
| `placeholder` | `string` | Placeholder text for inputs. |
| `variant` | `text` \| `number` \| `range` \| `date` \| `dateRange` \| `boolean` \| `select` \| `multiSelect` | Filter control type. |
| `options` | `{ label: string; value: string; count?: number; icon?: React.FC }[]` | Options for select and multiSelect filters. |
| `range` | `[number, number]` | Default min/max for range filters. |
| `unit` | `string` | Unit label for number/range filters (e.g. `"$"` or `"hr"`). |
| `icon` | `React.FC` | Optional icon for filter list items. |

### Filter variants

`variant` maps to specific UI controls:

- `text`: input field with text operators
- `number`: numeric input with numeric operators
- `range`: slider (simple toolbar) or min/max inputs (advanced filters)
- `date`: date picker
- `dateRange`: date range picker
- `boolean`: true/false select
- `select`: single choice faceted picker
- `multiSelect`: multi choice faceted picker

Operators and available variants are defined in `src/config/data-table.ts`.

## Sorting

Use `DataTableColumnHeader` to get sortable headers with a built-in dropdown menu:

```tsx
{
  id: "name",
  accessorKey: "name",
  header: ({ column }) => (
    <DataTableColumnHeader column={column} label="Name" />
  ),
  enableSorting: true,
}
```

`DataTableSortList` gives users a multi-column sorting picker. It syncs to the `sort` query param.

## Pagination

`useDataTable` is configured for manual pagination and requires `pageCount`. When you use `<DataTable />`, pagination is rendered automatically via `DataTablePagination`. For custom layouts, render `DataTablePagination` yourself.

```tsx
import { DataTablePagination } from "@/components/data-table/data-table-pagination";

<DataTablePagination table={table} pageSizeOptions={[10, 25, 50]} />
```

## Row selection and action bars

Enable selection by adding a checkbox column and using the selection state exposed by the table.

```tsx
import { Checkbox } from "@/components/ui/checkbox";

const columns: ColumnDef<Row>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && "indeterminate")
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(Boolean(value))}
        aria-label="Select all rows"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(Boolean(value))}
        aria-label="Select row"
      />
    ),
    enableSorting: false,
    enableHiding: false,
  },
  // other columns...
];
```

`DataTable` accepts an optional `actionBar` that appears when rows are selected:

```tsx
import { ActionBar } from "@/components/ui/action-bar";

const selectedCount = table.getFilteredSelectedRowModel().rows.length;

<DataTable
  table={table}
  actionBar={
    <ActionBar
      open={selectedCount > 0}
      onOpenChange={(open) => {
        if (!open) table.toggleAllRowsSelected(false);
      }}
    >
      {/* actions */}
    </ActionBar>
  }
/>
```

## Column visibility and pinning

Column visibility is handled by `DataTableViewOptions` (automatically included in toolbars).

Pin columns via `initialState.columnPinning`:

```tsx
const { table } = useDataTable({
  data,
  columns,
  pageCount,
  initialState: {
    columnPinning: { left: ["select"], right: ["actions"] },
  },
});
```

`DataTable` applies `getCommonPinningStyles` to headers and cells. If you render a custom table, call `getCommonPinningStyles({ column })` on each pinned cell.

## URL state and server integration

`useDataTable` keeps table state in the URL. It is configured for manual sorting/filtering/pagination, so you must fetch data based on the query params and return `pageCount`.

Use the built-in parsers to read the query params in your data layer:

```tsx
import {
  parseAsInteger,
  parseAsString,
  parseAsStringEnum,
  useQueryState,
} from "nuqs";

import { getFiltersStateParser, getSortingStateParser } from "@/lib/parsers";
import { getValidFilters } from "@/lib/data-table";

const columnIds = new Set(columns.map((column) => column.id).filter(Boolean) as string[]);

const [page] = useQueryState("page", parseAsInteger.withDefault(1));
const [perPage] = useQueryState("perPage", parseAsInteger.withDefault(20));
const [sorting] = useQueryState(
  "sort",
  getSortingStateParser<Row>(columnIds).withDefault([]),
);
const [filtersValue] = useQueryState("filters", parseAsString);
const [joinOperator] = useQueryState(
  "joinOperator",
  parseAsStringEnum(["and", "or"]).withDefault("and"),
);

const filters = React.useMemo(() => {
  if (!filtersValue) return [];
  const parsed = getFiltersStateParser<Row>(columnIds).parse(filtersValue) ?? [];
  return getValidFilters(parsed);
}, [filtersValue, columnIds]);

// Pass page, perPage, sorting, filters, joinOperator to your query.
```

You can rename query keys with `useDataTable({ queryKeys: { ... } })` if you need multiple tables on one page or want API-specific names.

## Loading states

Use `DataTableSkeleton` for consistent loading UIs:

```tsx
import { DataTableSkeleton } from "@/components/data-table/data-table-skeleton";

<DataTableSkeleton columnCount={6} rowCount={10} filterCount={2} />
```

## Keyboard shortcuts

These are built into `DataTableSortList`, `DataTableFilterList`, and `DataTableFilterMenu`:

- `Ctrl/Cmd + Shift + F` toggles the filter list or menu.
- `Ctrl/Cmd + Shift + S` toggles the sort list.
- `Backspace` or `Delete` on the trigger removes the last filter/sort.

## Component reference

- `useDataTable` - Initializes TanStack Table with URL-synced state and manual data control.
- `DataTable` - Renders the table, pagination, and optional action bar.
- `DataTableToolbar` - Standard toolbar with per-column filters + view options.
- `DataTableAdvancedToolbar` - Shell for advanced filter and sort controls.
- `DataTableFilterList` - Advanced filter builder with operators and AND/OR joins.
- `DataTableFilterMenu` - Command palette style filter picker.
- `DataTableSortList` - Multi-column sorting picker.
- `DataTablePagination` - Pagination control (standalone or in `DataTable`).
- `DataTableViewOptions` - Column visibility toggle.
- `DataTableColumnHeader` - Sortable/hideable column header UI.
- `DataTableSkeleton` - Loading placeholder.

## Gotchas

- Always set explicit `id` values on columns used for sorting or filtering.
- `useDataTable` is manual by design; your data fetching must respond to page/sort/filter updates.
- `enableAdvancedFilter: true` disables the simple toolbar filters. Use `DataTableFilterList` or `DataTableFilterMenu` instead.
- `pageCount` must be accurate for pagination to work correctly. When unknown, compute it from API metadata.
- Set `enableColumnFilter: true` on columns you want to appear in filter UIs, and provide `meta.options` for `select`/`multiSelect` variants.
- Provide `getRowId` when row IDs do not live at `row.id` to keep selection stable.
