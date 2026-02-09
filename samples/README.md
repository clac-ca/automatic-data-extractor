# ADE Engine-First Sample Corpus v1

## Purpose and Scope
This corpus is designed to validate ADE's engine behavior first:

- table detection under realistic spreadsheet layouts
- header-based field mapping using the default config template
- default-enabled normalization behavior (`full_name` transform)
- realistic mapped/unmapped outcomes in noisy operational exports

This corpus is not primarily a UI preview corpus.

## Scenario Matrix

| ID | File | Primary Challenge | Expected Behavior |
|---|---|---|---|
| S01 | `S01_clean_roster_alias_headers.xlsx` | clean baseline with alias headers | single table, strong name/email mapping, realistic unmapped business columns |
| S02 | `S02_two_tables_vertical_same_sheet.xlsx` | two vertically separated tables on one sheet | two table regions detected on one worksheet |
| S03 | `S03_preamble_stacked_headers.xlsx` | preamble + merged stacked headers | header block merge behavior with first/middle/last/email still detectable |
| S04 | `S04_offset_wide_mapping_pressure.xlsx` | offset wide export with duplicates + placeholder header | mapped and unmapped mix; duplicate and placeholder header reasons appear |
| S05 | `S05_multisheet_mixed_purpose_workbook.xlsx` | mixed-purpose workbook (instruction + intake + archive + lookup) | realistic multi-sheet input for future active/named sheet processing |
| S06 | `S06_full_name_normalization_cases.xlsx` | full-name format variants | full_name mapping with comma-order and whitespace normalization opportunities |
| S07 | `S07_contacts_export_quirks.csv` | CSV quirks (quoted commas, blanks, whitespace noise) | CSV ingestion parity with realistic export artifacts |
| S08 | `S08_side_by_side_tables_limitation.xlsx` | side-by-side logical tables in same row band | currently treated as one wide detected table (limitation sentinel) |

## File-by-File Notes

### S01 `S01_clean_roster_alias_headers.xlsx`
- Sheet: `Member Roster` (active)
- Rows: 110 data rows
- Headers include: `Given Name`, `M.I.`, `Surname`, `E-mail`
- Includes realistic business fields: `Member ID`, `Local`, `Employer`, `Classification`, `Hire Date`, `Status`, `Phone`
- Formatting: freeze pane `A2`, date format on hire date

### S02 `S02_two_tables_vertical_same_sheet.xlsx`
- Sheet: `Weekly Payroll` (active)
- Table A starts at row 6; table B starts at row 37
- Note/spacer block between tables to separate row bands
- Both tables include name/email header tokens

### S03 `S03_preamble_stacked_headers.xlsx`
- Sheet: `Settlement` (active)
- Rows 1-6 are merged preamble/title metadata
- Row 9 is group header; row 10 is leaf header
- Data starts row 11

### S04 `S04_offset_wide_mapping_pressure.xlsx`
- Sheet: `Operational Export` (active)
- Main table starts at `C4`
- 34 columns, 150 data rows
- Includes `Full Name`, `Email`, `Email Address`, and an intentionally blank header
- Includes hidden columns and footer summary note block

### S05 `S05_multisheet_mixed_purpose_workbook.xlsx`
- Sheets:
  - `README` (non-tabular instructions)
  - `May Intake` (active, main tabular sheet)
  - `Archive-Apr` (older valid table)
  - `Lookup` (small code table)

### S06 `S06_full_name_normalization_cases.xlsx`
- Sheet: `Names` (active)
- Includes comma-form names (`Last, First`), extra whitespace, mixed case, apostrophes/hyphens, and single-token names
- Focused on default `full_name` transform behavior

### S07 `S07_contacts_export_quirks.csv`
- UTF-8 CSV with 150 records
- Includes quoted commas in notes, occasional blank lines, and whitespace noise

### S08 `S08_side_by_side_tables_limitation.xlsx`
- Sheet: `Combined Export` (active)
- Left logical table in columns `A:G`
- Right logical table in columns `J:O`
- Same header row and overlapping row band by design

## Known Limitation Sentinel
`S08_side_by_side_tables_limitation.xlsx` intentionally documents a current limitation: side-by-side logical tables in one row band are typically interpreted as one wide table region.

## Authoring Standards
- Synthetic data only; no real PII.
- Deterministic content (no random values, no timestamps generated at runtime).
- Realistic operational context (locals, employers, classifications, statuses, payroll-like fields).
- Practical size and shape (not oversized, but realistic enough for engine behavior checks).

## Quick Local Commands

Parse sanity checks:

```bash
python3 - <<'PY'
from pathlib import Path
import csv
import openpyxl

root = Path('/Users/justinkropp/.codex/worktrees/7880/automatic-data-extractor/samples')
for path in sorted(root.glob('S0*.xlsx')):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    print(path.name, 'sheets=', wb.sheetnames)
    wb.close()

csv_path = root / 'S07_contacts_export_quirks.csv'
with csv_path.open('r', encoding='utf-8', newline='') as f:
    rows = sum(1 for _ in csv.reader(f))
print(csv_path.name, 'rows=', rows)
PY
```

Engine smoke run pattern:

```bash
cd /Users/justinkropp/.codex/worktrees/7880/automatic-data-extractor/backend
uv run ade-engine process file \
  --input /Users/justinkropp/.codex/worktrees/7880/automatic-data-extractor/samples/S01_clean_roster_alias_headers.xlsx \
  --config-package <materialized-default-config>
```
