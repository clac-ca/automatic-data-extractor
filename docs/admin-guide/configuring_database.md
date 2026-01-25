# Configuring the ADE Database

ADE standardizes on **Microsoft SQL Server / Azure SQL Database** via `mssql+pyodbc`.

Infrastructure admins choose the database by setting environment variables before the container starts.

---

## 1. Configuration model

ADE reads database settings from environment variables (prefix `ADE_`):

* `ADE_SQL_HOST`, `ADE_SQL_PORT`, `ADE_SQL_USER`, `ADE_SQL_PASSWORD`, `ADE_SQL_DATABASE`
  ADE derives the SQLAlchemy DSN from these values (this is the standard and only supported path).

* `ADE_DATABASE_ECHO`
  Enables SQLAlchemy "echo" logging (prints SQL statements and parameters).
  Use only for short-lived troubleshooting; it is very noisy and can expose data in logs.

* `ADE_DATABASE_LOG_LEVEL`
  Sets the SQLAlchemy logger level (e.g., `DEBUG`) without changing overall app logging.
  Useful for targeted SQL troubleshooting; still noisy and can expose data in logs.

* `ADE_SQL_ENCRYPT`, `ADE_SQL_TRUST_SERVER_CERTIFICATE`
  Optional SQL Server ODBC flags applied when building the DSN.

* `ADE_DATABASE_AUTH_MODE`
  Chooses authentication mode for SQL Server/Azure SQL:

  * `sql_password` – use username/password embedded in DSN (default).
  * `managed_identity` – use Azure Managed Identity (no credentials in DSN).

* `ADE_DATABASE_MI_CLIENT_ID`
  Optional GUID of a **user‑assigned** managed identity, if you use one. Leave unset for system‑assigned managed identity.

* `ADE_DATABASE_POOL_SIZE`
  Base connection pool size for SQL Server/Azure SQL (default `5`).

* `ADE_DATABASE_MAX_OVERFLOW`
  Extra connections allowed above the base pool size (default `10`).

* `ADE_DATABASE_POOL_TIMEOUT`
  Seconds to wait for a pooled connection before failing (default `30`).

* `ADE_DATABASE_POOL_RECYCLE`
  Seconds before recycling pooled connections (default `1800`).

ADE expects:

* Migrations to be applied before starting the API/worker (`ade dev`, `ade start`, and `ade api start` run them automatically; otherwise use `ade api migrate`).
* The same configuration (DSN + auth mode) for both runtime and migrations.

## 2. Using Azure SQL with SQL authentication

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
* For local dev, ensure the SQL container is running and `ADE_SQL_*` points at it.

### 2.1. Prerequisites

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

### 2.2. Environment variables

On the ADE container (local or Container Apps), set:

```env
# Replace PASSWORD with a URL-encoded value if it contains special characters.
ADE_SQL_HOST=sql-automaticdataextractor.database.windows.net
ADE_SQL_PORT=1433
ADE_SQL_DATABASE=sqldb-automaticdataextractor-prod
ADE_SQL_USER=svc_automaticdataextractor
ADE_SQL_PASSWORD=URL_ENCODED_PASSWORD
ADE_DATABASE_AUTH_MODE=sql_password
```

On startup, ADE will:

1. Connect to Azure SQL with the supplied credentials.
2. Expect the schema to be migrated already (`ade api migrate`).
3. Serve traffic using Azure SQL as the backing store.

**Recommended use**: staging, early production, or where managed identity is not yet available. Long‑term, consider switching to managed identity for secretless auth.

---

## 3. Using Azure SQL with Managed Identity (recommended for production)

Managed identity lets ADE authenticate to Azure SQL without embedding passwords.

### 3.1. Prerequisites

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

### 3.2. Environment variables

**System‑assigned managed identity**

```env
ADE_SQL_HOST=sql-automaticdataextractor.database.windows.net
ADE_SQL_PORT=1433
ADE_SQL_DATABASE=sqldb-automaticdataextractor-prod
ADE_DATABASE_AUTH_MODE=managed_identity

# For system-assigned MI, leave this unset:
# ADE_DATABASE_MI_CLIENT_ID=
```

**User‑assigned managed identity**

```env
ADE_SQL_HOST=sql-automaticdataextractor.database.windows.net
ADE_SQL_PORT=1433
ADE_SQL_DATABASE=sqldb-automaticdataextractor-prod
ADE_DATABASE_AUTH_MODE=managed_identity
ADE_DATABASE_MI_CLIENT_ID=<your-user-assigned-mi-client-id>

# Optional but common:
# AZURE_CLIENT_ID=<your-user-assigned-mi-client-id>
```

On startup, ADE will:

* Use `DefaultAzureCredential` inside the container to obtain an access token for `https://database.windows.net/.default`.
* Pass that token to the SQL Server ODBC driver in the correct format.
* Serve traffic with **no credentials in the DSN** after migrations are applied (`ade api migrate`).

**Recommended use**: production ADE deployments on Azure Container Apps.

---

## 4. Choosing the right auth mode

**Authentication choice for Azure SQL:**

* Start with **`sql_password`** if you need a simple bring‑up.
* Move to **`managed_identity`** as your long‑term, secure, secretless configuration.

Once the environment variables are set and the image includes the required ODBC driver (as in the provided Dockerfile), `ade start` (or `ade api start`) will run migrations automatically. If you are launching the API/worker manually, run `ade api migrate` to bootstrap the schema first.
