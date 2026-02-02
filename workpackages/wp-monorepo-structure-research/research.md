# Monorepo Structure Research Notes

## Constraints and preferences (ADE)

- Keep deployables separate: `ade-api`, `ade-worker`, `ade-web`.
- No shared Python modules between API and worker (standalone services).
- One Docker image that can run roles separately or together (via compose).
- Standard nginx serving for the web UI.
- Repo should feel conventional and readable to new contributors.

## Evaluation rubric

- Deployable boundaries are obvious (service folders).
- Each service owns its dependencies and CLI.
- Minimal bespoke tooling; defaults and common conventions.
- Works well with Docker/Compose.
- Easy to split services into separate repos later.

## Reference repos (24)

Apps/packages monorepos (common structure):
- https://github.com/t3-oss/create-t3-turbo
- https://github.com/vercel/turborepo
- https://github.com/NiGhTTraX/ts-monorepo
- https://github.com/John-pels/monorepo-template
- https://github.com/byCedric/expo-monorepo-example
- https://github.com/owieth/turborepo-example
- https://github.com/thmsmtylr/turborepo-starter
- https://github.com/ycjcl868/monorepo
- https://github.com/nrwl/nx
- https://github.com/nrwl/nx-examples
- https://github.com/calcom/cal.com
- https://github.com/supabase/supabase
- https://github.com/supabase/stripe-sync-engine

Backend/frontend split repos:
- https://github.com/testdrivenio/fastapi-react
- https://github.com/Buuntu/fastapi-react
- https://github.com/yagnesh97/fastapi-react-template
- https://github.com/jsonfm/fastapi-react-ecommerce
- https://github.com/0xCodeFuture/fastapi-react

Microservices demos:
- https://github.com/GoogleCloudPlatform/microservices-demo
- https://github.com/microservices-demo/microservices-demo
- https://github.com/open-telemetry/opentelemetry-demo
- https://github.com/spring-petclinic/spring-petclinic-microservices
- https://github.com/dotnet-architecture/eShopOnContainers

## Structure matrix (summary)

| Repo | Layout style | Notes |
| --- | --- | --- |
| t3-oss/create-t3-turbo | apps/ + packages/ | Multi-app JS monorepo with shared packages. |
| vercel/turborepo | monorepo tool + examples | Standard `apps` + `packages` examples. |
| NiGhTTraX/ts-monorepo | apps/ + packages/ | Explicit separation of apps vs packages. |
| John-pels/monorepo-template | apps/ + packages/ | Template using workspaces + turbo. |
| byCedric/expo-monorepo-example | apps/ + packages/ | Expo + web with shared packages. |
| owieth/turborepo-example | apps/ + packages/ | Turborepo starter with apps/packages. |
| thmsmtylr/turborepo-starter | apps/ + packages/ | Next.js + packages template. |
| ycjcl868/monorepo | apps/ + packages/ | pnpm + turborepo template. |
| nrwl/nx | monorepo tool | Nx workspace supports apps/libs. |
| nrwl/nx-examples | apps/libs | Example Nx workspace with multiple apps. |
| calcom/cal.com | apps/ + packages/ | Multiple apps plus shared packages. |
| supabase/supabase | apps/ + packages/ | Multiple apps + shared packages. |
| supabase/stripe-sync-engine | packages/ | Two-package monorepo. |
| testdrivenio/fastapi-react | backend/ + frontend/ | Simple full-stack split. |
| Buuntu/fastapi-react | backend/ + frontend/ + nginx | Cookiecutter template with nginx. |
| yagnesh97/fastapi-react-template | backend/ + frontend/ + nginx | Full-stack template with infra folders. |
| jsonfm/fastapi-react-ecommerce | backend/ + frontend/ | E-commerce with API/UI split. |
| 0xCodeFuture/fastapi-react | backend/ + frontend/ + database | Full-stack split with DB folder. |
| GoogleCloudPlatform/microservices-demo | per-service dirs | Many microservices in one repo. |
| microservices-demo/microservices-demo | per-service/deploy dirs | Sock Shop demo with multiple services. |
| open-telemetry/opentelemetry-demo | src/ per-service | Many services under src/. |
| spring-petclinic-microservices | per-service dirs | Spring microservices demo. |
| eShopOnContainers | per-service dirs | .NET microservices reference app. |

## Patterns observed

1) `apps/` + `packages/` is the most common monorepo shape when multiple deployables exist.
2) `backend/` + `frontend/` is the most common layout for a single API + UI project.
3) Microservice demos keep services in sibling folders or a shared `src/` tree and rely on Docker/Compose/Kubernetes for orchestration.
4) Per-service dependency ownership is the norm when teams want clean boundaries and future repo splits.

## Recommendation (primary)

Use a standard monorepo layout with `apps/` for deployables and no root Python distribution:

```
repo/
├─ apps/
│  ├─ ade-api/        # FastAPI service
│  │  ├─ pyproject.toml
│  │  ├─ uv.lock
│  │  └─ src/ade_api/...
│  ├─ ade-worker/     # Worker service
│  │  ├─ pyproject.toml
│  │  ├─ uv.lock
│  │  └─ src/ade_worker/...
│  └─ ade-web/        # React/Vite
│     ├─ package.json
│     ├─ package-lock.json
│     └─ src/...
├─ Dockerfile
├─ docker-compose.yaml
├─ docs/
├─ scripts/
└─ .github/
```

This matches the most common multi-deployable monorepo pattern and keeps API/worker boundaries hard while allowing a single image with role-based commands.

## Recommendation (fallback)

If you want a simpler tree for newcomers:

```
repo/
├─ ade-api/
├─ ade-worker/
├─ ade-web/
├─ docker/
├─ docs/
└─ scripts/
```

This is less common in monorepos but very direct; it still preserves service boundaries.

## Migration plan outline

1) Lock the target structure (apps/ vs services/). Update docs with new paths.
2) Move each service to its folder (or keep as-is if already under apps/).
3) Ensure each service has its own `pyproject.toml` and `uv.lock` (API/worker) and web has `package.json` + lock.
4) Update Dockerfile to install deps per service and copy web dist to nginx path.
5) Update Compose files to run `ade-api`, `ade-worker`, and the nginx entrypoint as separate containers.
6) Update `setup.sh` and developer docs to run per-service commands.
7) Validate: local dev, compose up, API health, web loads, worker starts.

## Risks and mitigations

- **Dev UX complexity:** Provide a simple root Makefile/justfile wrapper instead of a root Python package.
- **Dependency drift:** Keep per-service `uv.lock` and `package-lock.json` committed.
- **Future shared code:** Add `packages/` only when needed; keep it optional until then.
