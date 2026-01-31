# Automatic Data Extractor (ADE)

ADE is a self-hostable document extraction service with an **API**, **Web UI**, and a background **worker**.

For local development, ADE runs with **Postgres** and **Azurite** (an Azure Blob Storage emulator) so it works out of the box with no external services.  
For production, ADE connects to an existing **Postgres** database and **Azure Blob Storage** account.

---

## Prerequisites

Install these first:

- **Docker** (includes Docker Compose)
  - Windows:
    ```bash
    winget install --id Docker.DockerDesktop
    ```
  - macOS:
    ```bash
    brew install --cask docker
    ```
  - Linux (Ubuntu/Debian):
    ```bash
    curl -fsSL https://get.docker.com | sh
    ```
- **Git**
  - Windows:
    ```bash
    winget install --id Git.Git
    ```
  - macOS:
    ```bash
    brew install git
    ```
  - Linux (Ubuntu/Debian):
    ```bash
    sudo apt-get update
    sudo apt-get install -y git
    ```
- **Optional (recommended for contributors):** VS Code Dev Container workflow
  - VS Code
    - Windows:
      ```bash
      winget install --id Microsoft.VisualStudioCode
      ```
    - macOS:
      ```bash
      brew install --cask visual-studio-code
      ```
    - Linux (Ubuntu/Debian):
      ```bash
      sudo snap install code --classic
      ```
  - Dev Containers extension
    ```bash
    code --install-extension ms-vscode-remote.remote-containers
    ```

---

## Get the code

### Clone with Git
1. Run:

```bash
git clone https://github.com/clac-ca/automatic-data-extractor
cd automatic-data-extractor
```

---

## Quickstart (local)

This starts ADE + local Postgres + local Azurite.

```bash
docker compose up --build
```

Open:

* `http://localhost:8000`

Stop:

```bash
docker compose down
```

Reset local data (database + storage + ADE data):

```bash
docker compose down -v
```

---

## Production

Production uses **external Postgres** and **external Azure Blob Storage**.
The default deployment runs a single container that starts **API**, **worker**, and **web (nginx)**.

```bash
docker compose -f docker-compose.prod.yaml pull
docker compose -f docker-compose.prod.yaml up -d
```

Alternate (split services across containers):

```bash
docker compose -f docker-compose.prod.split.yaml pull
docker compose -f docker-compose.prod.split.yaml up -d
```

Create a `.env` file next to the compose file you run (minimum):

```env
ADE_DATABASE_URL=postgresql+psycopg://user:pass@pg.example.com:5432/ade?sslmode=verify-full

# Azure Blob (choose one auth method supported by your deployment)
ADE_BLOB_ACCOUNT_URL=https://<account>.blob.core.windows.net
ADE_BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net

ADE_BLOB_CONTAINER=ade
ADE_SECRET_KEY=<long-random-secret>
```

See `.env.example` for the full set of supported environment variables.

Tip: for a single container with a subset of services, use `ade start --services api,web`
or set `ADE_START_SERVICES=api,web`.

---

## Development (VS Code Dev Container)

If you’re contributing, the fastest setup is a dev container:

1. Install Docker + VS Code + the Dev Containers extension
2. Open the repo in VS Code
3. Run **“Dev Containers: Reopen in Container”**

---

## Troubleshooting

* See logs: `docker compose logs -f`
* “Start fresh”: `docker compose down -v`
