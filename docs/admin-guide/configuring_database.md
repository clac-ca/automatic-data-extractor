# Configuring the ADE Database

ADE standardizes on **PostgreSQL** via `postgresql+psycopg`.

Infrastructure admins choose the database by setting environment variables before the container starts.

---

## 1. Configuration model

ADE reads database settings from environment variables (prefix `ADE_`):

* `ADE_DATABASE_URL`
  Canonical SQLAlchemy DSN used everywhere (API, worker, migrations). Must include host,
  username, and database name. When `ADE_DATABASE_AUTH_MODE=password`, the URL must include
  a password. Set `sslmode=verify-full` in the URL for production.

* `ADE_DATABASE_AUTH_MODE`
  Chooses authentication mode for Postgres:

  * `password` – use username/password embedded in the URL (default).
  * `managed_identity` – use Azure Managed Identity (token-as-password).

* `ADE_DATABASE_SSLROOTCERT`
  Optional CA bundle path when using `verify-full`.

* `ADE_DATABASE_POOL_SIZE`
  Base connection pool size (default `5`).

* `ADE_DATABASE_MAX_OVERFLOW`
  Extra connections allowed above the base pool size (default `10`).

* `ADE_DATABASE_POOL_TIMEOUT`
  Seconds to wait for a pooled connection before failing (default `30`).

* `ADE_DATABASE_POOL_RECYCLE`
  Seconds before recycling pooled connections (default `1800`).

ADE expects:

* Migrations to be applied before starting the API/worker (`ade dev`, `ade start`, and
  `ade api start` run them automatically; otherwise use `ade api migrate`).
* The same configuration (DSN + auth mode) for both runtime and migrations.

## 2. Using Azure Database for PostgreSQL with password auth

This is often the easiest way to get started.

### 2.1. Prerequisites

* An Azure Database for PostgreSQL instance (e.g. `pg-automaticdataextractor-prod.postgres.database.azure.com`).
* A database and role with appropriate permissions (at least `CREATE`, `USAGE`, and table-level DML).

Example (simplified):

```sql
CREATE ROLE ade_app LOGIN PASSWORD '<STRONG_PASSWORD>';
GRANT CONNECT ON DATABASE ade TO ade_app;
GRANT USAGE ON SCHEMA public TO ade_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ade_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ade_app;
```

### 2.2. Environment variables

On the ADE container (local or Container Apps), set:

```env
ADE_DATABASE_URL=postgresql+psycopg://ade_app:URL_ENCODED_PASSWORD@pg-automaticdataextractor-prod.postgres.database.azure.com:5432/ade?sslmode=verify-full
ADE_DATABASE_SSLROOTCERT=/path/to/DigiCertGlobalRootG2.crt.pem
ADE_DATABASE_AUTH_MODE=password
```

On startup, ADE will:

1. Connect to Postgres with the supplied credentials.
2. Expect the schema to be migrated already (`ade api migrate`).
3. Serve traffic using Postgres as the backing store.

---

## 3. Using Managed Identity (recommended for production)

Managed identity lets ADE authenticate to Azure Database for PostgreSQL without embedding passwords.

### 3.1. Prerequisites

1. **Enable managed identity** on the ADE Azure Container App:

   * Either system‑assigned identity.
   * Or a user‑assigned managed identity.

2. **Grant the identity access** in Postgres:

   ```sql
   CREATE ROLE "<identity-name>" LOGIN;
   GRANT CONNECT ON DATABASE ade TO "<identity-name>";
   GRANT USAGE ON SCHEMA public TO "<identity-name>";
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "<identity-name>";
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "<identity-name>";
   ```

3. Ensure networking/firewall rules allow the Container App to reach the Postgres server.

### 3.2. Environment variables

```env
ADE_DATABASE_URL=postgresql+psycopg://<identity-name>@pg-automaticdataextractor-prod.postgres.database.azure.com:5432/ade?sslmode=verify-full
ADE_DATABASE_SSLROOTCERT=/path/to/DigiCertGlobalRootG2.crt.pem
ADE_DATABASE_AUTH_MODE=managed_identity
```

DefaultAzureCredential will select the appropriate managed identity (system-assigned or user-assigned)
based on the hosting environment.

On startup, ADE will:

* Use `DefaultAzureCredential` inside the container to obtain an access token for
  `https://ossrdbms-aad.database.windows.net/.default`.
* Pass that token to psycopg as the password.
* Serve traffic with **no credentials in the DSN** after migrations are applied (`ade api migrate`).

---

## 4. Choosing the right auth mode

**Authentication choice for Azure Database for PostgreSQL:**

* Start with **`password`** if you need a simple bring‑up.
* Move to **`managed_identity`** as your long‑term, secure, secretless configuration.

Once the environment variables are set, `ade start` (or `ade api start`) will run migrations
automatically. If you are launching the API/worker manually, run `ade api migrate` to bootstrap
 the schema first.
