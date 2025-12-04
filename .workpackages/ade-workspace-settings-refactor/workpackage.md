---

> **Agent instruction (read first):**
>
> * Treat this workpackage as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` -> `[x]` as you complete tasks, and add new items when you discover more work.
> * Prefer small, incremental commits aligned to checklist items.
> * If you must change the plan, **update this document first**, then the code.

---

## Work Package Checklist

* [x] Add `GET /meta/versions` to ade-api that returns installed `ade-api` + `ade-engine` versions
* [x] Add a simple "About / Versions" UI in ade-web that shows ade-web version + fetched api/engine versions
* [x] Wire ade-web build version into the UI (single constant from build env / package.json)
* [x] Add minimal tests (API endpoint) + docs snippet ("Where to find versions")

> **Agent note:**
> Keep commits small: (1) API endpoint, (2) web UI modal, (3) wiring build version, (4) tests/docs.

---

# Workpackage: Show Installed Versions in ade-web (ade-web + ade-api + ade-engine)

## 1. Objective

**Goal:**
Show the currently installed versions of:

* `ade-web` (the frontend build)
* `ade-api` (installed python distribution)
* `ade-engine` (installed python distribution)

**You will:**

* Add a tiny API endpoint that returns installed package versions.
* Add a visible UI location in ade-web to display them.

**The result should:**

* Be obvious to users/devs where to find versions (one click).
* Always show versions without needing run telemetry or complex event logic.

---

## 2. Context (What you are starting from)

* `ade-api` and `ade-engine` are installed in the same instance/runtime (so the API can report both installed versions).
* `ade-web` is a separate build artifact (so it can report its own version locally).
* No "deployment metadata" required -- only installed `x.y.z` version strings.

**Constraints:**

* Keep it simple.
* Prefer a single endpoint and a single UI page/modal.

---

## 3. Target architecture / structure (ideal)

**Summary:**

* `ade-api`: exposes `/meta/versions` -> `{ ade_api: "x.y.z", ade_engine: "x.y.z" }`
* `ade-web`: shows `ade-web` version from a local constant and fetches `/meta/versions` for the backend.

```text
apps/
  ade-api/
    src/ade_api/
      meta/
        routes.py                # NEW: GET /meta/versions
      infra/
        versions.py              # NEW: helper to read installed versions
  ade-web/
    src/
      shared/version.ts          # NEW: WEB_VERSION constant
      api/meta.ts                # NEW: fetchVersions()
      components/VersionsModal.tsx  # NEW: displays all versions
      components/AppMenu.tsx     # add "About / Versions" entry
tests/
  apps/ade-api/tests/
    test_meta_versions.py        # NEW
docs/
  versions.md (or existing docs) # NEW or updated section
```

---

## 4. Design (for this workpackage)

### 4.1 Design goals

* **Dead simple:** only installed versions.
* **Discoverable:** one obvious place in the UI (menu -> "About / Versions").
* **Stable contract:** endpoint response is tiny and unlikely to change.

### 4.2 Key components / modules

* **ade-api** `GET /meta/versions`
* **ade-web** versions modal/page + a small fetcher

### 4.3 Key flows / pipelines

* ade-web loads -> user opens "About / Versions"
* ade-web immediately shows `ade-web` version (local), and fetches `/meta/versions`
* render `ade-api` and `ade-engine` versions once loaded

### 4.4 Open questions / decisions

* **Decision:** only show installed versions (`x.y.z`), no git sha/build timestamp.
* **Decision:** UI location = app menu item "About / Versions" that opens a modal.

---

## 5. Implementation & notes for agents

### 5.1 ade-api: `/meta/versions`

**Helper: `infra/versions.py`**

```py
# apps/ade-api/src/ade_api/infra/versions.py
from importlib.metadata import version as dist_version, PackageNotFoundError

def installed_version(*dist_names: str) -> str:
    """
    Return the first installed version that matches any provided distribution name.
    Keeps things robust across naming differences.
    """
    for name in dist_names:
        try:
            return dist_version(name)
        except PackageNotFoundError:
            continue
    return "unknown"
```

**Route:**

```py
# apps/ade-api/src/ade_api/meta/routes.py
from fastapi import APIRouter
from ade_api.infra.versions import installed_version

router = APIRouter(tags=["meta"])

@router.get("/meta/versions")
def get_versions():
    return {
        "ade_api": installed_version("ade-api", "ade_api"),
        "ade_engine": installed_version("ade-engine", "ade_engine"),
    }
```

**Plumbing**

* Register `router` in the main FastAPI app (where other routers are included).

**Minimal API test**

```py
# apps/ade-api/tests/test_meta_versions.py
def test_meta_versions(client):
    resp = client.get("/meta/versions")
    assert resp.status_code == 200
    data = resp.json()
    assert "ade_api" in data
    assert "ade_engine" in data
    assert isinstance(data["ade_api"], str)
    assert isinstance(data["ade_engine"], str)
```

---

### 5.2 ade-web: show versions

#### A) Define web version constant

If you are using Vite, simplest is to inject `VITE_APP_VERSION` at build time (from `package.json`).

```ts
# apps/ade-web/src/shared/version.ts
export const ADE_WEB_VERSION = import.meta.env.VITE_APP_VERSION ?? "unknown";
```

**Build step (simple):**

* Set `VITE_APP_VERSION` in your build pipeline to `package.json` version.

  * Example: `VITE_APP_VERSION=$(node -p "require('./package.json').version")`

#### B) Fetch backend versions

```ts
# apps/ade-web/src/api/meta.ts
export type VersionsResponse = {
  ade_api: string;
  ade_engine: string;
};

export async function fetchVersions(): Promise<VersionsResponse> {
  const res = await fetch("/meta/versions", { credentials: "include" });
  if (!res.ok) throw new Error("Failed to fetch versions");
  return await res.json();
}
```

#### C) Versions Modal

```tsx
# apps/ade-web/src/components/VersionsModal.tsx
import React from "react";
import { ADE_WEB_VERSION } from "../shared/version";
import { fetchVersions, VersionsResponse } from "../api/meta";

export function VersionsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [data, setData] = React.useState<VersionsResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setData(null);
    setError(null);
    fetchVersions().then(setData).catch((e) => setError(e.message ?? "Error"));
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-header">
          <h2>About / Versions</h2>
          <button onClick={onClose}>Close</button>
        </div>

        <div className="section">
          <div className="row">
            <span className="label">ade-web</span>
            <span className="value">{ADE_WEB_VERSION}</span>
          </div>

          <div className="row">
            <span className="label">ade-api</span>
            <span className="value">{data?.ade_api ?? (error ? "unavailable" : "loading...")}</span>
          </div>

          <div className="row">
            <span className="label">ade-engine</span>
            <span className="value">{data?.ade_engine ?? (error ? "unavailable" : "loading...")}</span>
          </div>
        </div>

        {error && <div className="error">Could not load backend versions: {error}</div>}
      </div>
    </div>
  );
}
```

#### D) Entry point in UI (menu)

* Add "About / Versions" to your existing app menu / user menu / help menu.
* Clicking opens the modal.

This is the only UX choice you need to make.

---

### 5.3 Documentation

Add a short doc section (or README snippet):

* "To see installed versions: open **About / Versions** in the UI"
* "For API automation: call `GET /meta/versions`"

---

### 5.4 Done criteria

* UI shows **ade-web** version instantly.
* UI displays **ade-api** and **ade-engine** installed versions from `/meta/versions`.
* Endpoint works in local + deployed.
* One minimal API test added.
* Docs updated.

---

If you tell me what frontend stack you are using (Vite vs Next vs something else), I can tailor the exact "web version" injection to match, but the workpackage above will work as-is for most React/Vite setups.
