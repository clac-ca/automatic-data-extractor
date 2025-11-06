## Frontend Structure (DO NOT LET DRIFT AWAY FROM THIS STRUCTURE

```
apps/web/
├─ package.json
├─ tsconfig.json
├─ vite.config.ts
├─ react-router.config.ts                # { appDirectory: "src/app", ssr: false } (SPA)
└─ src/
   ├─ ui/                                # shared presentational components
   ├─ generated/                         # OpenAPI-generated types (openapi.d.ts)
   │  └─ openapi.d.ts
   ├─ shared/                            # cross-route libs/types
   │  └─ api.ts
   └─ app/
      ├─ AppProviders.tsx                # global providers (QueryClient, etc.)
      ├─ root.tsx                        # document shell + <Outlet/> + <Scripts/>
      ├─ routes.ts                       # export default flatRoutes()
      └─ routes/                         # file-based routes (dotted siblings)
         ├─ _index.tsx                   # "/"
         ├─ login.tsx                    # "/login"
         ├─ auth.callback.tsx            # "/auth/callback"
         ├─ setup.tsx                    # "/setup"

         ├─ workspaces/route.tsx         # shared layout for all /workspaces/* (optional but common)
         ├─ workspaces._index/route.tsx  # "/workspaces"
         ├─ workspaces.new/route.tsx     # "/workspaces/new"

         ├─ workspaces.$workspaceId/route.tsx                    # "/workspaces/:workspaceId"
         ├─ workspaces.$workspaceId._index/route.tsx             # "/workspaces/:workspaceId"
         ├─ workspaces.$workspaceId.documents._index/route.tsx
         ├─ workspaces.$workspaceId.documents.$documentId/route.tsx
         ├─ workspaces.$workspaceId.jobs._index/route.tsx
         ├─ workspaces.$workspaceId.configurations._index/route.tsx
         ├─ workspaces.$workspaceId.settings._index/route.tsx

         └─ $.tsx                           # catch-all 404
```

### Required config

```ts
// vite.config.ts
import { defineConfig } from "vite";
import { reactRouter } from "@react-router/dev/vite";

export default defineConfig({
  plugins: [reactRouter()],
});
```

```ts
// react-router.config.ts
import type { Config } from "@react-router/dev/config";

export default {
  appDirectory: "src/app",
  ssr: false,
} satisfies Config;
```

```ts
// src/app/routes.ts
import type { RouteConfig } from "@react-router/dev/routes";
import { flatRoutes } from "@react-router/fs-routes";

export default flatRoutes() satisfies RouteConfig;
```

## Routing & Naming Rules (v7)

* **Index route:** `_index.tsx` is the index of its parent (e.g., `workspaces._index`).
* **Dynamic params:** `$id` → `:id` (e.g., `workspaces.$workspaceId`).
* **Nesting by name:** Use dotted segments to encode nested URLs/layouts (e.g., `workspaces.$workspaceId.documents._index`).
* **Folders for organisation:** A route can be a folder containing `route.tsx`. Helper files in that folder are ignored by routing.
* **Pathless layout group:** Leading underscore creates a layout-only segment without a URL segment.
* **Trailing underscore:** Keeps the URL segment but prevents nested layout (e.g., `parent_.child.tsx`).
* **Catch-all:** `$.tsx` for 404s.

## Data (SPA mode)

* Use `clientLoader` and `clientAction` for data fetching/mutations.
* Prefer relative API paths (`/api/v1/...`) so dev/prod behave the same behind the proxy.

Type-safe route modules:

```ts
import type { Route } from "../+types/workspaces.$workspaceId";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  // params.workspaceId is typed
  return null;
}

export default function Workspace({ loaderData }: Route.ComponentProps) {
  return <div><Outlet /></div>;
}
```

## Commands

```bash
npm run dev                     # usually run from repo root
npx react-router build          # build SPA bundles
npx react-router routes --json  # print discovered route tree
```

## Do / Don't

* **Do** keep page UI in `src/app/routes/**`; extract shared UI to `src/ui/**`.
* **Do** colocate helper components/hooks in a route folder alongside `route.tsx`.
* **Do** add an explicit index child whenever you introduce a new parent layout.
* **Don't** hand-register routes in `routes.ts`; rely on `flatRoutes()`.
* **Don't** place child route files inside the parent directory unless the directory name encodes the full dotted path.
* **Don't** hardcode absolute API origins; use relative `/api/...`.

## API Client & Types

- Run `npm run openapi-typescript` (root package script) to refresh `src/generated/openapi.d.ts`. A checked-in copy keeps typecheck working without the backend.
- Use the shared `src/shared/api/client.ts` instance (built on `openapi-fetch`) for all HTTP calls; pass typed `params`/`body` based on the generated `paths` definitions.
- Import schema types directly from the alias `@openapi` (e.g. `components["schemas"]["DocumentRecord"]`) instead of hand-rolled wrappers. Keep any request/response helpers colocated with the route that owns them.

## Key Docs

1. https://reactrouter.com/how-to/file-route-conventions
2. https://reactrouter.com/api/framework-conventions/react-router.config.ts
3. https://reactrouter.com/tutorials/quickstart
4. https://reactrouter.com/api/other-api/dev
5. https://reactrouter.com/explanation/type-safety
