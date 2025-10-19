# Automatic Data Extractor

Mono-repo skeleton for:
- `backend/` — FastAPI (will be generated from a template)
- `frontend/` — React Router (framework mode, file-based routes)

> To scaffold later:
> - Frontend: `npm create react-router@latest frontend`
> - Backend:  `cookiecutter https://github.com/Tobi-De/cookiecutter-fastapi --no-input project_name="Backend" project_slug="backend"`

This repository intentionally starts empty at the root. Run the generators above when you're ready, then iterate toward the agreed structure and conventions.

## Commands

```bash
# dev
npm install
npm run dev

# CI / agent
npm run ci   # prints JSON summary (setup/test/build/routes)

# local production
npm run build
npm run start

# docker production
docker build -t app .
docker run --rm -p 8000:8000 --env-file backend/.env app
```
