# Configuring the ADE Database

ADE supports two database backends:

* **SQLite** (default)
* **Microsoft SQL Server / Azure SQL Database** via `mssql+pyodbc`

Infrastructure admins choose the backend by setting environment variables before the container starts.

---

## 1. Quick comparison: SQLite vs Azure SQL

### SQLite (default)

**What it is**

* A file‑based database embedded in the ADE container.
* By default stored under `/app/data/db/ade.sqlite` (or `./data/db/ade.sqlite` in local runs).

**Pros**

* ✅ **Zero external dependencies** – no separate DB server to deploy or manage.
* ✅ **Simple local setup** – ideal for dev, demos, and single‑node test environments.
* ✅ **Backups are just files** – you can snapshot or copy the `data/` volume.

**Cons**

* ⚠️ **Not designed for high concurrency** – file‑locking and write contention become an issue under heavier load or multiple writers.
* ⚠️ **Tied to the container’s storage** – harder to scale out horizontally; rolling deployments with shared volumes can hit locking errors.
* ⚠️ **No built‑in HA/replication** – all resilience must come from host/volume backups.

**When to use**

* Local development and integration testing.
* Small, single‑instance ADE deployments where traffic and write volume are low.
* Environments where running a managed SQL service is not feasible.

---

### Azure SQL / Microsoft SQL Server

**What it is**

* A fully managed SQL database (Azure SQL Database or SQL Server in Azure) accessed over the network using `mssql+pyodbc`.

**Pros**

* ✅ **Production‑grade concurrency** – designed for many concurrent readers and writers.
* ✅ **Durability & HA** – built‑in backups, point‑in‑time restore, availability features from Azure.
* ✅ **Horizontal scaling** – ADE instances can scale out; all share the same database.
* ✅ **Good fit for Azure Container Apps** – avoids SQLite file locking issues across revisions / replicas.

**Cons**

* ⚠️ **External dependency** – requires provisioning and operating Azure SQL (or SQL Server) and networking.
* ⚠️ **Cost** – billed as a separate service; sizing and cost management are your responsibility.
* ⚠️ **Operational complexity** – firewall rules, identity, and connectivity need to be configured correctly.

**When to use**

* Any **production** or **staging** deployment of ADE.
* Scenarios with multiple containers, blue/green or rolling deployments, or higher traffic.
* Environments where data durability and availability are non‑negotiable.

---

## 2. Configuration model

ADE reads database settings from environment variables (prefix `ADE_`):

* `ADE_DATABASE_URL`
  Full SQLAlchemy DSN string (URL). If omitted, ADE defaults to SQLite.

* `ADE_DATABASE_ECHO`
  Enables SQLAlchemy "echo" logging (prints SQL statements and parameters).
  Use only for short-lived troubleshooting; it is very noisy and can expose data in logs.

* `ADE_DATABASE_LOG_LEVEL`
  Sets the SQLAlchemy logger level (e.g., `DEBUG`) without changing overall app logging.
  Useful for targeted SQL troubleshooting; still noisy and can expose data in logs.

* `ADE_DATABASE_AUTH_MODE`
  Chooses authentication mode for SQL Server/Azure SQL:

  * `sql_password` – use username/password embedded in DSN (default).
  * `managed_identity` – use Azure Managed Identity (no credentials in DSN).

* `ADE_DATABASE_MI_CLIENT_ID`
  Optional GUID of a **user‑assigned** managed identity, if you use one. Leave unset for system‑assigned managed identity.

ADE expects:

* Migrations to be applied before starting the API/worker (`ade start` and `ade dev` run them automatically; otherwise use `ade migrate`).
* The same configuration (DSN + auth mode) for both runtime and migrations.

---

## 3. Using SQLite (default)

**Minimal configuration (local/dev)**

You don’t need to set any DB env vars:

```env
# No ADE_DATABASE_URL set → ADE uses SQLite automatically
```

ADE will create (or reuse) a file‑based SQLite database under the `data/db/` directory mounted into the container.

**Optional: custom SQLite location**

If you want to override the path:

```env
ADE_DATABASE_URL=sqlite:///./data/db/ade.sqlite
```

Use this only for single‑instance setups. For Container Apps with multiple revisions/replicas, prefer Azure SQL.

### 3.1 Optional: SQLite concurrency tuning

ADE applies safe SQLite defaults for mixed read/write workloads. You can override them if you need to reduce
`database is locked` errors or tune durability/performance tradeoffs:

* `ADE_DATABASE_SQLITE_JOURNAL_MODE` (default `WAL`) – allows readers to proceed during writes.
* `ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS` (default `30000`) – how long SQLite waits on locks before failing.
* `ADE_DATABASE_SQLITE_SYNCHRONOUS` (default `NORMAL`) – set `FULL` for maximum durability.
* `ADE_DATABASE_SQLITE_BEGIN_MODE` (optional `DEFERRED|IMMEDIATE|EXCLUSIVE`) – `IMMEDIATE` grabs the write
  reservation up front, which can prevent lock errors for queue/worker claims.

Example:

```env
ADE_DATABASE_SQLITE_BUSY_TIMEOUT_MS=30000
ADE_DATABASE_SQLITE_BEGIN_MODE=IMMEDIATE
ADE_DATABASE_SQLITE_SYNCHRONOUS=NORMAL
```

---

## 4. Using Azure SQL with SQL authentication

This is often the easiest way to get started with Azure SQL.

### ODBC driver prerequisites (local/dev)

To connect to Azure SQL from a local machine (or run Alembic migrations locally), install the ODBC driver first; otherwise `pyodbc` will fail with errors like `libodbc.so.2: cannot open shared object file`.

* **Debian/Ubuntu**: add the Microsoft repo first (`curl -sSL -O https://packages.microsoft.com/config/ubuntu/$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2)/packages-microsoft-prod.deb && sudo dpkg -i packages-microsoft-prod.deb && sudo apt-get update`) then `sudo ACCEPT_EULA=Y apt-get install -y unixodbc msodbcsql18`
* **macOS**: `brew install unixodbc` and install the Microsoft ODBC Driver 18 for SQL Server package.
* **Windows**: install the Microsoft ODBC Driver 18 for SQL Server (standard installer).

If you see `Login timeout expired (HYT00)` during startup/migrations:

* Verify the host/port is reachable (e.g., `nc -vz <server> 1433` or `sqlcmd -S <server> -U <user> -P <pass>`).
* Check firewall/private endpoint rules to ensure your machine/container can reach the SQL Server endpoint.
* Confirm the DSN matches your auth mode (SQL password vs managed identity) and has `driver=ODBC Driver 18 for SQL Server` plus `Encrypt`/`TrustServerCertificate` as required.
* For local dev, switch to SQLite: `ADE_DATABASE_URL=sqlite:///./data/db/ade.sqlite`.

### 4.1. Prerequisites

* An Azure SQL Database (e.g. `sqldb-automaticdataextractor-prod`) on a server (e.g. `sql-automaticdataextractor.database.windows.net`).
* A SQL login/user with appropriate permissions (at least `db_datareader`, `db_datawriter`, and whichever DDL rights you assign for migrations).

Example (simplified):

```sql
-- in master
CREATE LOGIN svc_automaticdataextractor WITH PASSWORD = '<STRONG_PASSWORD>';

-- in the ADE database
CREATE USER svc_automaticdataextractor FROM LOGIN svc_automaticdataextractor;
ALTER ROLE db_datareader ADD MEMBER svc_automaticdataextractor;
ALTER ROLE db_datawriter ADD MEMBER svc_automaticdataextractor;
-- optionally: ALTER ROLE db_ddladmin ADD MEMBER svc_automaticdataextractor;
```

Ensure firewall/VNet rules allow connections from your Container App.

### 4.2. Environment variables

On the ADE container (local or Container Apps), set:

```env
# Replace PASSWORD with a URL-encoded value if it contains special characters.
ADE_DATABASE_URL=mssql+pyodbc://svc_automaticdataextractor:URL_ENCODED_PASSWORD@sql-automaticdataextractor.database.windows.net:1433/sqldb-automaticdataextractor-prod?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

ADE_DATABASE_AUTH_MODE=sql_password
# ADE_DATABASE_MI_CLIENT_ID is not used in this mode
```

On startup, ADE will:

1. Connect to Azure SQL with the supplied credentials.
2. Expect the schema to be migrated already (`ade migrate`).
3. Serve traffic using Azure SQL as the backing store.

**Recommended use**: staging, early production, or where managed identity is not yet available. Long‑term, consider switching to managed identity for secretless auth.

---

## 5. Using Azure SQL with Managed Identity (recommended for production)

Managed identity lets ADE authenticate to Azure SQL without embedding passwords.

### 5.1. Prerequisites

1. **Enable managed identity** on the ADE Azure Container App:

   * Either system‑assigned identity.
   * Or a user‑assigned managed identity (record its client ID).

2. **Grant the identity access** in Azure SQL:

   In the ADE database:

   ```sql
   CREATE USER [<identity-name>] FROM EXTERNAL PROVIDER;

   ALTER ROLE db_datareader ADD MEMBER [<identity-name>];
   ALTER ROLE db_datawriter ADD MEMBER [<identity-name>];
   -- plus db_ddladmin or a migration-specific role if this identity will apply migrations
   ```

3. Ensure networking/firewall rules allow the Container App to reach the SQL server.

### 5.2. Environment variables

**System‑assigned managed identity**

```env
ADE_DATABASE_URL=mssql+pyodbc://@sql-automaticdataextractor.database.windows.net:1433/sqldb-automaticdataextractor-prod?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
ADE_DATABASE_AUTH_MODE=managed_identity

# For system-assigned MI, leave this unset:
# ADE_DATABASE_MI_CLIENT_ID=
```

**User‑assigned managed identity**

```env
ADE_DATABASE_URL=mssql+pyodbc://@sql-automaticdataextractor.database.windows.net:1433/sqldb-automaticdataextractor-prod?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
ADE_DATABASE_AUTH_MODE=managed_identity
ADE_DATABASE_MI_CLIENT_ID=<your-user-assigned-mi-client-id>

# Optional but common:
# AZURE_CLIENT_ID=<your-user-assigned-mi-client-id>
```

On startup, ADE will:

* Use `DefaultAzureCredential` inside the container to obtain an access token for `https://database.windows.net/.default`.
* Pass that token to the SQL Server ODBC driver in the correct format.
* Serve traffic with **no credentials in the DSN** after migrations are applied (`ade migrate`).

**Recommended use**: production ADE deployments on Azure Container Apps.

---

## 6. Choosing the right backend

**Use SQLite when:**

* You’re developing or testing ADE locally.
* You’re running a single container instance with low concurrency.
* You accept that the DB is tied to the container’s volume and not highly available.

**Use Azure SQL when:**

* You’re running ADE in **production** or **staging**.
* You need resilience, backups, and horizontal scaling.
* You’re deploying on Azure Container Apps and want safe rolling updates without SQLite file locking issues.

**Authentication choice for Azure SQL:**

* Start with **`sql_password`** if you need a simple bring‑up.
* Move to **`managed_identity`** as your long‑term, secure, secretless configuration.

Once the environment variables are set and the image includes the required ODBC driver (as in the provided Dockerfile), `ade start` will run migrations automatically. If you are launching the API/worker manually, run `ade migrate` to bootstrap the schema first.
