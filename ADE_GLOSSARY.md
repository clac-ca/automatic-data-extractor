# ADE\_GLOSSARY.md

> **Scope:** ADE extracts **tables** (rows & columns) from spreadsheets and table‑like PDF pages, then maps observed **columns** to **canonical column types** using code‑based **detection\_logic**, with optional **transformation\_logic** and **validation\_logic**.
> **Purpose:** This glossary is optimized for **programming & data‑modeling**. It defines the canonical terms, their **storage locations**, **keys**, and how they **compose** into a runnable configuration.

**Conventions**

* **UI names:** Title Case (e.g., *Column Type*).
* **API keys / storage keys:** `snake_case` (e.g., `column_type`).
* **Enums:** lowercase strings (e.g., `row_type: "header"`).
* **Immutability:** Deployed configurations are immutable **Snapshots**; “Live” is a pointer to a `snapshot_id`.

---

## 1) Terms (single reference table)

| UI Term                 | API Key                | Kind             | Stored In                          | Identity / Key                | Definition                                                                                                                  |                 |          |                                             |
| ----------------------- | ---------------------- | ---------------- | ---------------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------- | --------------- | -------- | ------------------------------------------- |
| Document Type           | `document_type`        | Entity           | Snapshot, Manifest                 | string                        | Category of document (e.g., `remittance`, `invoice`, `roster`). Drives schema & catalog choice.                             |                 |          |                                             |
| Document                | `document`             | Entity           | Manifest                           | path/name or opaque id        | A single file to ingest (XLSX/CSV/PDF). Processed under one `document_type`.                                                |                 |          |                                             |
| Page                    | `page`                 | Entity           | Manifest                           | zero‑based index              | Spreadsheet worksheet/tab or PDF page.                                                                                      |                 |          |                                             |
| Table                   | `table`                | Entity           | Manifest                           | (page\_index, table\_index)   | Contiguous rectangular area on a Page that behaves as a table (one `header_row` + data rows).                               |                 |          |                                             |
| Row Type                | `row_type`             | Entity/Enum      | Manifest                           | \`"header"                    | "data"                                                                                                                      | "group\_header" | "note"\` | Role assigned to each row by Header Finder. |
| Header Row              | `header_row`           | Entity           | Manifest                           | row index                     | The row in a table that names the columns (winning `row_type="header"`).                                                    |                 |          |                                             |
| Column (Observed)       | `column`               | Entity           | Manifest                           | column index (per table)      | A physical column in an extracted table; has `header_text` and sampled `values`.                                            |                 |          |                                             |
| Column Type (Canonical) | `column_type`          | Entity           | Snapshot                           | string key                    | The canonical meaning for a column (e.g., `member_first_name`, `government_id`).                                            |                 |          |                                             |
| Column Catalog          | `column_catalog`       | Entity           | Snapshot                           | list of keys                  | Registry of available `column_type`s for a `document_type`.                                                                 |                 |          |                                             |
| Schema                  | `schema`               | Entity           | Snapshot                           | embedded                      | Allowed/required `column_type`s & constraints for a `document_type`.                                                        |                 |          |                                             |
| Profile                 | `profile`              | Entity           | Snapshot (baked) or Live overrides | string key                    | Optional per‑source overrides (e.g., extra synonyms, parameters).                                                           |                 |          |                                             |
| Synonyms                | `synonyms`             | Logic metadata   | Snapshot → `column_type`           | list\[string]                 | Alternate header names/patterns used during detection.                                                                      |                 |          |                                             |
| Detection Logic         | `detection_logic`      | Logic            | Snapshot → `column_type`           | code + digest                 | Code that decides if a **column** matches a **column\_type**; returns `bool` (or score).                                    |                 |          |                                             |
| Transformation Logic    | `transformation_logic` | Logic            | Snapshot → `column_type`           | code + digest                 | Code that normalizes cell values after mapping.                                                                             |                 |          |                                             |
| Validation Logic        | `validation_logic`     | Logic            | Snapshot → `column_type`           | code + digest                 | Code that verifies transformed values meet constraints (optional but recommended).                                          |                 |          |                                             |
| Header Finder           | `header_finder`        | Process          | Snapshot                           | struct                        | Row‑level rules & decision policy that segment pages and pick `header_row`.                                                 |                 |          |                                             |
| Row Rule                | `row_rule`             | Logic            | Snapshot → `header_finder.rules[]` | name + digest                 | Per‑row boolean/score function used by Header Finder.                                                                       |                 |          |                                             |
| Column Mapping          | `column_mapping`       | Output           | Manifest                           | (table\_index, column\_index) | Assignment of observed **column** → **column\_type** with confidence & audit.                                               |                 |          |                                             |
| Scores / Score Vector   | `score_vector`         | Scoring          | Manifest                           | per decision                  | Totals across candidates before the winner is chosen (optional if purely boolean).                                          |                 |          |                                             |
| Confidence              | `confidence`           | Scoring          | Manifest                           | float 0..1                    | Normalized certainty derived from scores/tie margins.                                                                       |                 |          |                                             |
| Needs Review            | `needs_review`         | Scoring          | Manifest                           | boolean                       | Flag for tie/low confidence or validation failure.                                                                          |                 |          |                                             |
| Audit Log               | `audit_log`            | Output           | Manifest                           | list                          | Trace: matches, logic results, deltas/scores, transforms, validations.                                                      |                 |          |                                             |
| Snapshot                | `snapshot`             | Versioned bundle | Snapshot Store                     | `snapshot_id` (ULID/UUID)     | Immutable, self‑contained configuration for a `document_type` (catalog + types + schema + header\_finder + baked profiles). |                 |          |                                             |
| Live Pointer            | `live_snapshot_id`     | Control          | Live Registry                      | mapping                       | Current Live `snapshot_id` per `document_type` (and optional per‑profile overrides).                                        |                 |          |                                             |
| Manifest (Run Report)   | `manifest`             | Output           | Run Store                          | `run_id`                      | Machine‑readable output of a run, pinning the exact `snapshot_id`.                                                          |                 |          |                                             |
| Digest                  | `digest`               | Integrity        | Snapshot, Manifest                 | sha256                        | Hash of embedded code (detection/transform/validation/row\_rule) for audit & integrity.                                     |                 |          |                                             |

---

## 2) Minimal Data Model (programmer‑friendly)

> These are **canonical shapes**. Implementation can be SQLite (JSON columns), Postgres (jsonb + indexes), or filesystem blobs + an index table.

### 2.1 Snapshot (immutable, self‑contained)

```json
{
  "snapshot": {
    "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
    "document_type": "remittance",
    "status": "draft",                       // draft | live | archived
    "title": "2025-09-17 Broaden SIN; name transform fix",
    "note": "Added 'soc ins #' synonym, tweaked first-name transform.",
    "created_at": "2025-09-17T14:00:00Z",
    "created_by": "user:justin",

    "column_catalog": [
      "member_first_name",
      "member_last_name",
      "government_id",
      "employee_number",
      "amount_gross",
      "amount_net",
      "email"
    ],

    "column_types": {
      "member_first_name": {
        "display_name": "Member First Name",
        "synonyms": ["first name","first_name","firstname","first-name","f name","fname","first*"],
        "detection_logic": {
          "language": "python",
          "entrypoint": "detect",
          "digest": "sha256:9a61…",
          "code": "def detect(header_text, values, **ctx):\n    ht=(header_text or '').lower()\n    for s in ['first name','first_name','firstname','first-name','f name','fname','first']:\n        if s in ht: return True\n    sample=[str(v or '') for v in values[:200]]\n    letters=sum(1 for v in sample if v.replace(' ','').replace('-','').replace(\"'\",'').isalpha())\n    return sample and (letters/len(sample) >= 0.8)\n"
        },
        "transformation_logic": {
          "language": "python",
          "entrypoint": "transform",
          "digest": "sha256:bc88…",
          "code": "def transform(value, **ctx):\n    s=str(value or '').strip().lower()\n    return ' '.join(w.capitalize() for w in s.split())\n"
        },
        "validation_logic": {
          "language": "python",
          "entrypoint": "validate",
          "digest": "sha256:1f2e…",
          "code": "import re\n\ndef validate(value, **ctx):\n    s=str(value or '').strip()\n    return bool(re.match(r\"^[A-Za-z][A-Za-z '\\-]*$\", s))\n"
        },
        "params": {}                          // optional typed params passed via **ctx
      },

      "government_id": {
        "display_name": "Government ID",
        "synonyms": ["sin","social insurance number","social ins #","soc ins #"],
        "detection_logic": { "language": "python", "entrypoint": "detect", "digest": "sha256:…", "code": "…" },
        "transformation_logic": { "language": "python", "entrypoint": "transform", "digest": "sha256:…", "code": "…" },
        "validation_logic": { "language": "python", "entrypoint": "validate", "digest": "sha256:…", "code": "…" }
      }
    },

    "schema": {
      "required_column_types": ["government_id","amount_gross"],
      "optional_column_types": ["member_first_name","member_last_name","employee_number","amount_net","email"],
      "constraints": {
        "government_id": {"unique": true},
        "amount_gross": {"min": 0}
      }
    },

    "header_finder": {
      "rules": [
        {
          "name": "has_header_words",
          "language": "python",
          "entrypoint": "run",
          "digest": "sha256:ab12…",
          "code": "def run(row_cells, **ctx):\n    WORDS={'employee','sin','gross','net','email'}\n    text=' '.join(str(c or '').lower() for c in row_cells)\n    return any(w in text for w in WORDS)\n"
        },
        {
          "name": "row_is_dense_text",
          "language": "python",
          "entrypoint": "run",
          "digest": "sha256:cd34…",
          "code": "def run(row_cells, **ctx):\n    texts=sum(1 for c in row_cells if str(c or '').isalpha())\n    return texts/max(1,len(row_cells)) >= 0.6\n"
        }
      ],
      "decision": {
        "row_types": ["header","data","group_header","note"],
        "scoring": "boolean-additive",        // or "score-additive"
        "tie_breaker": "unknown->needs_review"
      }
    },

    "profiles": {
      "clac.default": {
        "synonyms_overrides": {
          "government_id": ["SIN","Social Insurance #","Soc Ins #"]
        },
        "parameters": { "amount_gross": {"currency": "CAD"} }
      }
    }
  }
}
```

**Notes (programmatic):**

* A Snapshot is **the only** deployable configuration unit. It is **immutable** once published.
* `column_catalog` is the **allow‑list** of `column_type` keys considered during mapping.
* Code blocks are embedded with a **sha256 `digest`** for audit & caching.
* You may also support `python_path` instead of `code` for packaged deployments.

---

### 2.2 Live Registry (one pointer; optional per‑profile overrides)

```json
{
  "live": {
    "remittance": {
      "live_snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",
      "updated_at": "2025-09-17T15:05:02Z",
      "updated_by": "user:ops",
      "profile_overrides": {
        "clac.default": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V"
      }
    },
    "invoice": {
      "live_snapshot_id": "snap_01J7YYZZ…"
    }
  }
}
```

---

### 2.3 Manifest (run output) — pins the exact configuration

```json
{
  "manifest": {
    "run_id": "run_01J8R0XY…",
    "generated_at": "2025-09-17T15:20:00Z",
    "document_type": "remittance",
    "snapshot_id": "snap_01J8PQ3RDX8K6PX0ZA5G2T3N4V",     // reproducibility
    "profile": "clac.default",
    "document": "ACME_July_2025.xlsx",
    "pages": [
      {
        "index": 0,
        "tables": [
          {
            "header_row": 3,
            "rows": [
              {"index": 1, "row_type": "note"},
              {"index": 3, "row_type": "header"},
              {"index": 4, "row_type": "data"}
            ],
            "columns": [
              {"index": 0, "header_text": "Emp #"},
              {"index": 1, "header_text": "First Name"},
              {"index": 2, "header_text": "SIN"},
              {"index": 3, "header_text": "Gross $"}
            ],
            "column_mapping": [
              {
                "column_index": 1,
                "column_type": "member_first_name",
                "confidence": 0.96,
                "needs_review": false,
                "score_vector": {"member_first_name": 9, "member_last_name": -3, "email": -2},
                "audit_log": [
                  "synonym match: 'first name'",
                  "value heuristic: letters_ratio=0.92",
                  "transform: title_case applied",
                  "validate: ok"
                ]
              },
              {
                "column_index": 2,
                "column_type": "government_id",
                "confidence": 0.91,
                "needs_review": false,
                "score_vector": {"government_id": 10, "employee_number": -4, "amount_gross": -3},
                "audit_log": [
                  "pattern match: SIN regex",
                  "transform: stripped spaces/hyphens",
                  "validate: checksum ok"
                ]
              }
            ]
          }
        ]
      }
    ],
    "stats": {
      "tables_detected": 1,
      "columns_mapped": 2,
      "needs_review": 0
    }
  }
}
```

---

## 3) Type Contracts (for implementers)

> Using TypeScript‑style interfaces to make shapes precise (these map 1:1 to the JSON above).

```ts
// ---------- Keys & Enums ----------
type DocumentType = string;          // "remittance" | "invoice" | ...
type RowType = "header" | "data" | "group_header" | "note";
type SnapshotStatus = "draft" | "live" | "archived";

// ---------- Logic ----------
interface CodeBlock {
  language: "python";
  entrypoint: string;                // "detect" | "transform" | "validate" | "run"
  code?: string;                     // inline code
  python_path?: string;              // optional module path instead of code
  digest: string;                    // sha256 over source for integrity & caching
}

// ---------- Column Type ----------
interface ColumnTypeDef {
  display_name: string;
  synonyms: string[];
  detection_logic: CodeBlock;
  transformation_logic: CodeBlock;
  validation_logic?: CodeBlock;
  params?: Record<string, unknown>;
}

// ---------- Snapshot ----------
interface Snapshot {
  snapshot_id: string;
  document_type: DocumentType;
  status: SnapshotStatus;
  title?: string;
  note?: string;
  created_at: string;
  created_by: string;

  column_catalog: string[];
  column_types: Record<string, ColumnTypeDef>;

  schema: {
    required_column_types: string[];
    optional_column_types: string[];
    constraints?: Record<string, unknown>;
  };

  header_finder: {
    rules: Array<{
      name: string;
      language: "python";
      entrypoint: "run";
      digest: string;
      code?: string;
      python_path?: string;
    }>;
    decision: {
      row_types: RowType[];
      scoring: "boolean-additive" | "score-additive";
      tie_breaker: "unknown->needs_review";
    };
  };

  profiles?: Record<
    string,                                  // profile key
    {
      synonyms_overrides?: Record<string, string[]>;
      parameters?: Record<string, Record<string, unknown>>;
    }
  >;
}

// ---------- Live registry ----------
interface LiveRegistry {
  [document_type: string]: {
    live_snapshot_id: string;
    updated_at: string;
    updated_by: string;
    profile_overrides?: Record<string, string>; // profile_key -> snapshot_id
  };
}

// ---------- Manifest (run output) ----------
interface Manifest {
  run_id: string;
  generated_at: string;
  document_type: DocumentType;
  snapshot_id: string;
  profile?: string;
  document: string;
  pages: Array<{
    index: number;
    tables: Array<{
      header_row: number;
      rows: Array<{ index: number; row_type: RowType }>;
      columns: Array<{ index: number; header_text: string }>;
      column_mapping: Array<{
        column_index: number;
        column_type: string;
        confidence?: number;
        needs_review: boolean;
        score_vector?: Record<string, number>;
        audit_log: Array<string>;
      }>;
    }>;
  }>;
  stats?: Record<string, number>;
}
```

---

## 4) Versioning (simplified: Snapshots + Live)

**What users manage:**

* **Snapshots**: Create Draft → Edit → Test → **Publish as Live** → (if needed) **Rollback** to prior Snapshot.
* **Live pointer**: One per `document_type` (optionally per profile) pointing to the current `snapshot_id`.

**What the system persists:**

* **Immutable Snapshots** with embedded logic + `digest`s.
* **Live Registry** mapping `document_type` (and optional `profile`) → `live_snapshot_id`.
* **Manifests** that pin `snapshot_id` for perfect reproducibility.

**Why this is simplest:**

* One publish/rollback object.
* No cross‑resource pin management.
* Still supports advanced needs via embedded profiles & header rules.

---

## 5) Invariants & Constraints (programmer checklist)

* **Immutability:** A `snapshot` with `status: live|archived` is immutable. New edits require `draft` cloned from an existing snapshot.
* **Catalog Inclusion:** All keys in `schema.required_column_types` and `schema.optional_column_types` **must** exist in `column_types` and appear in `column_catalog`.
* **Header Finder Safety:** `row_rule.code` and `column_type.*_logic.code` are **pure** (no I/O; deterministic).
* **Digests:** `digest` must match the code or module to support caching + audit.
* **Manifest Pinning:** Every manifest stores the exact `snapshot_id`; re‑runs with the same inputs yield identical decisions.
* **Profiles:** Profile overrides are **resolved inside** the snapshot to avoid out‑of‑band pins.
* **Tables:** Table boundaries cannot overlap on the same page.
* **Needs Review:** If `validation_logic` fails or winner margin < threshold, set `needs_review: true`.

---

## 6) How it fits together (at a glance)

```mermaid
flowchart TD
  A[Live Registry] -->|document_type| B[Snapshot (immutable)]
  B --> C[Header Finder]
  B --> D[Column Types + Catalog + Schema]
  E[Document (XLSX/PDF)] --> F[Pages]
  F --> G[Tables]
  G --> C
  G --> H[Columns (Observed)]
  C -->|row_type + header_row| G
  H --> D
  D --> I[Column Mapper]
  I --> J[Column Mapping + Scores + Needs Review + Audit]
  J --> K[Manifest (pins snapshot_id)]
```

---

## 7) Practical dev notes

* **Compile & cache** logic blocks by `digest` to avoid re‑loading code during a run.
* **Allow `python_path`** so production can use packaged modules while dev uses inline `code`.
* **Locale/Params:** pass `**ctx` into detectors/transformers (e.g., `{locale:"en-CA", currency:"CAD"}` from profiles).
* **Testing:** keep a corpus; show diffs in GUI when comparing two `snapshot_id`s (impact report).
* **Security:** execute code in a sandboxed interpreter with time/memory limits.

---

**This ADE\_GLOSSARY.md supersedes prior copies.**
Use the terms, keys, and shapes above as the baseline for code, storage, and UI.
