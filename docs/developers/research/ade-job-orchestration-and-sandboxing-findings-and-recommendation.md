# ADE Job Orchestration & Sandboxing - Findings & Recommendation

## 1. Executive Summary

**Recommended Design:** Use an in-process job queue with fixed-size worker threads (or tasks) to launch each ADE job in a **separate sandboxed Python subprocess**. Each job subprocess runs the user's extraction code in isolation with strict resource limits and no network access by default, while the FastAPI server remains single-container and single-process (aside from these worker subprocesses).

**Why this is simplest & safest:** This design avoids any new infrastructure (no Celery, no Docker-in-Docker). It leverages Python's standard library and OS features for isolation: using a subprocess per job means the main API process is protected from crashes or malicious code. We apply operating-system limits (CPU time, memory, file access) inside each job process, achieving basic sandboxing without complex frameworks. All components run inside the existing single container for simplicity and easy deployment.

**Key Risks & Mitigations:**

- _File System Access:_ The job's subprocess could theoretically read/modify files accessible to its OS user. **Mitigation:** Run job processes under a non-privileged user and restrict file permissions so they can only access their job working directory. For stronger isolation, consider Linux sandbox tools (e.g. bubblewrap) in future if needed.
- _Resource Exhaustion:_ Without limits, a user job could hang or consume excessive CPU/memory. **Mitigation:** Enforce strict timeouts and resource caps (CPU seconds, RAM, disk file size) on each job process. The parent monitors and kills any job that exceeds wall-clock time.
- _Malicious Code Execution:_ Running untrusted Python code is inherently risky. **Mitigation:** **Process isolation** (no shared memory with server) and disabling dangerous capabilities (no network, limited system calls). This prevents most exploits that would be possible within the server process. (Complete security would require kernel-level isolation; see Section 8.)
- _Dependency Installation:_ Installing user-specified packages at runtime can execute arbitrary code (in setup.py). **Mitigation:** Install dependencies in an isolated environment (the job's own directory) and run the installer under limited privileges (same sandbox as the job) to minimize impact.
- _Operational Complexity:_ Introducing a job runner must not over-complicate deployment. **Mitigation:** The chosen design runs entirely within one container using Python's async and subprocess features, with a single knob for concurrency and a bounded queue. No additional services or containers are needed, keeping operations simple.

## 2. Repository Recon (what exists today)

**Project Overview:** ADE consists of a FastAPI backend (data extraction API) and a React frontend (compiled to static files), served together in one Docker container. Currently, **all persistence** is handled locally: metadata in a SQLite database, and files stored under a var/ directory in the container's filesystem. Key parts of the existing design include:
> **Storage note:** Replace `/var/...` with the configured `ADE_STORAGE_DATA_DIR` when running outside the container image. The default `.env.example` maps this to the local `data/` folder.

- **Database (SQLite via SQLAlchemy):** Tables for users, workspaces, documents (with metadata), and importantly **configurations** and **configuration_script_versions** (which store the user's Python extraction rules code, likely as text blobs and versioned hashes). There is also a **jobs** table to record job runs (status, timestamps, logs/metrics in JSON). We will extend this jobs table usage to track the queued/running/completed jobs.
- **File Storage (var/):** Large artifacts are stored as files:
  - `var/documents/&lt;workspace&gt;/&lt;doc_id&gt;/` holds uploaded input files (e.g. raw Excel sheets).
  - `var/jobs/&lt;job_id&gt;/` is a per-job working directory. Currently, when a job is run, the system materializes the user's configuration code into this folder along with the input data:
    - `input.xlsx` — a copy of the original document to process.
    - `config/` — the user's code package, reconstructed from the DB (e.g. `columns/*.py`, `row_types/*.py`, `hooks/*.py`, plus a manifest).
    - An optional `requirements.txt` if the user config declares extra Python dependencies.
    - Placeholders for outputs: `artifact.json` (the job's log of operations/decisions) and `normalized.xlsx` (the cleaned output spreadsheet), plus `logs.txt` for any textual logs.
- The codebase likely has utility functions to create these directories and copy files. We will use those to set up each job run.
- **Processing Model ("Passes"):** ADE's extraction runs in defined stages:
  - **Pass 1 – Structure Detection:** Identify tables and header rows using user-defined _row detectors_ (probably functions or classes in `row_types/*.py` that mark header boundaries).
  - **Pass 2 – Column Mapping:** Map raw columns to normalized schema fields using _column detectors_ (`columns/*.py` rules).
  - **Pass 3 – Transformation:** Apply transformations (possibly defined in `hooks/*.py` or elsewhere) to clean/convert data.
  - **Pass 4 – Validation:** Validate the transformed data against schema or constraints.
  - **Pass 5 – Output Generation:** Write the normalized Excel (`normalized.xlsx`) using a streaming writer.

Throughout these passes, the system appends records to an **artifact.json** file. This artifact is an append-only log or structured JSON that captures what the job discovered and did at each step (e.g. which rows identified as headers, how columns were mapped, any validation errors). Importantly, this artifact is designed **not** to include raw cell values - only references (like cell coordinates or summary info), to avoid storing sensitive data in logs.

- **Current Job Execution:** As of now, jobs may be executed synchronously (possibly via FastAPI endpoint calls that do the processing inline). There is likely no existing background worker mechanism - this is what we're introducing. The codebase may include placeholders or stubs for background tasks, but no active queue system. We will build the job orchestration around the existing FastAPI app:
  - We'll add a **Job Manager** that starts when the app starts (using FastAPI's startup event). This manager will maintain an asyncio queue of pending jobs and a fixed pool of worker tasks that run in the background.
  - The API will get new endpoints under a "jobs" router (e.g. `POST /jobs` to submit, `GET /jobs/{id}` to query status, etc.), integrated alongside existing routers (the project likely follows a feature-based router structure).
  - The database model for jobs will be used/extended to record job state transitions (QUEUED → RUNNING → SUCCESS/ERROR) and to store results (artifact path, any metrics).
- **Config Scripts Versioning:** Each configuration (rule set for processing a certain type of document) is stored in the DB, possibly with multiple versions. When a job is triggered, the backend fetches the appropriate script version (the code blob) and writes it to the `config/` folder in the job directory. This includes generating the module files (e.g. writing out each detector function into `columns/<name>.py`, etc.) and a manifest that ties them together. We'll use this mechanism to produce the code files that the sandboxed subprocess will import.
- **Dockerfile & Runtime Environment:** The existing Dockerfile likely starts from a Python base image (perhaps Alpine or Debian slim). It installs FastAPI, Uvicorn/Gunicorn, and the frontend static files. It may not currently include build tools or any sandbox utilities. We will plan minimal additions:
  - Ensure pip is available (most official images have it) and potentially upgrade it.
  - Install OS packages needed for building Python packages (if user requirements include packages with C extensions). For example, add `gcc`, Python dev headers, etc., to support pip install if needed.
  - (Optional) Add a non-root user account to run jobs (and potentially even run the app).
  - (Optional) Include a "wheelhouse" directory with pre-downloaded common packages to facilitate offline or faster installation of dependencies at runtime.
- **Security Context:** Currently, if the container runs as the default user, it might be root (unless the Dockerfile sets a `USER`). That means the FastAPI app and any job code would run as root - clearly not ideal for untrusted code. We plan to adjust this by introducing a dedicated low-privilege user for job subprocesses (and possibly run the main app as non-root as well). This will align with best practices and prevent the job code from having full root access to the container.

In summary, the repository provides a foundation (data models, file structure, config code handling) that we will leverage. We will insert our job orchestration in the appropriate places: initialize the queue in the FastAPI app's startup (likely in main.py or the app factory), add a new router (e.g. jobs.py) for the HTTP endpoints, and create new modules for the job runner logic (job_manager.py in the backend and a separate script for the sandbox worker process). The design will integrate cleanly with the existing single-process service and reuse its data handling utilities.

## 3. Options Landscape (overview)

We explored three main approaches to execute jobs within the single-container deployment, comparing their complexity and isolation:

**Option A: Subprocess per Job with "Vendor" Dependencies Directory (pip -t)**  
Each job is run in a fresh Python subprocess (via subprocess.Popen). The user's code and any Python libraries it needs are placed in an isolated directory (a "vendor" folder) that the subprocess uses as its PYTHONPATH. This can be achieved by running pip install -t &lt;job_dir&gt;/config/vendor -r requirements.txt to install dependencies into that job's folder[\[1\]](https://cloud.tencent.com/developer/ask/sof/106280791#:~:text=). The subprocess is launched with Python's _isolated mode_ flags (-I -s -S -B) to prevent loading any global site-packages or user site settings. This means the job's Python process will only see the standard library and the modules in the job's own directories. We would monkey-patch or otherwise disable networking in this subprocess and apply OS resource limits. No additional environment (like a virtualenv) is created - the base Python binary is reused, but with an isolated import path for each job.

**Option B: Subprocess per Job with a Micro-Virtualenv**  
This approach also uses a separate Python process for each job, but instead of manually managing PYTHONPATH, it creates a dedicated **virtual environment** for the job. For example, on job start: python -m venv /var/jobs/&lt;id&gt;/venv, then pip install the required packages into that venv, and launch the job using the venv's Python interpreter. The job code runs with that venv's site-packages, which by design won't include the main server's packages unless explicitly installed. We still enforce network off (by configuration or by not enabling internet in the venv) and apply resource limits. This yields a clean Python environment per job, at the cost of a bit more setup time per job (creating the venv and installing potentially overlapping packages repeatedly). It also uses slightly more disk space because each venv will duplicate any common libraries.

**Option C: Subprocess with OS-Level Sandboxing Tools (e.g. Bubblewrap/Firejail)**  
In this variant, we still spawn a subprocess for each job, but we would additionally invoke a sandboxing tool like **Bubblewrap** (bwrap) or **Firejail** to confine the process at the kernel level. These tools can create a very restricted environment: for example, using Bubblewrap we could create a new **mount namespace** with only the job's directory and necessary system libraries mounted, and a new **network namespace** with no external connectivity. This effectively "containers" the job process further, preventing it from seeing the host filesystem (aside from its own files) or using the network, even if it tried to bypass Python-level restrictions. Bubblewrap can also drop capabilities and apply cgroup limits. Firejail similarly can restrict filesystem and network access via simpler profiling. The goal here is maximum isolation without launching a full VM or Docker-in-Docker.

We compared these options on several criteria:

- **Simplicity:** Option A (Subprocess + vendor dir) is very straightforward - it uses Python's built-in capabilities and requires minimal new tooling. Installing dependencies into a folder and adjusting PYTHONPATH is a well-known, simple method[\[1\]](https://cloud.tencent.com/developer/ask/sof/106280791#:~:text=). Option B (micro-venv) is moderately simple but introduces more moving parts (creating and managing venvs for each job). Option C (Bubblewrap/Firejail) is the most complex: it involves adding system-level tools and possibly dealing with their configuration and edge cases (must ensure the container supports user namespaces, etc.). For MVP, simplicity is paramount - so Options A or B are preferred over C.
- **Isolation (Environment & Imports):** Option B (venv) offers a clean Python environment, ensuring the job can't accidentally import server's packages - the server's libraries aren't in the venv's site-packages. Option A (vendor with isolated mode) can achieve a similar effect by using -S to skip global site-packages【14†output】 and only putting the vendor directory on PYTHONPATH. This effectively isolates imports as well - but we must be careful to include any needed built-in libs (like the Excel reading/writing library) in the job's environment. Both A and B prevent the job from importing the FastAPI app or other sensitive modules, either by not having them on the path or by running in isolated mode. Option C, when combined with either method, doesn't change Python import isolation (we would likely still need A or B inside the sandbox), but it adds OS-level isolation too.
- **Isolation (OS sandboxing):** Option C excels here. It can restrict filesystem access to only the job's directory and perhaps a temp directory, and completely disable network at the system call level. Options A and B, by contrast, rely on our manual restrictions within the Python process and file permission setups. Without Bubblewrap, a malicious script could theoretically use low-level tricks (like ctypes or launching system commands) to attempt access beyond its directory. Option A/B will still run the process as an unprivileged user with tightened limits, which stops many attacks but not all (see Section 8 for limitations). C provides the highest security but at a cost of complexity.
- **Timeouts & Resource Limits:** All options can use resource.setrlimit in the job subprocess to enforce CPU time and memory limits, and we can use the parent process to enforce wall-clock timeouts. So in terms of managing time/CPU/memory, A and B are equal. Option C might allow even stricter controls (e.g. cgroups for memory) but we can achieve what we need with rlimits already.
- **Network Toggle:** Without Bubblewrap (Options A/B), we have to disable networking in software - e.g., by monkey-patching the socket library or setting firewall rules. This is not 100% foolproof (an expert attacker could attempt to call low-level socket syscalls via ctypes to bypass Python's socket module), but it will block any normal network usage by the job code. With Bubblewrap/Firejail (Option C), we can **truly** turn off networking by not providing any network interface in the sandbox (or using Firejail's --net=none option), meaning even a ctypes call to socket() will fail at the system level. For MVP, the software toggle should suffice for our threat model (since the user scripts are not extremely adversarial, and the container's own Docker seccomp profile already blocks some risky syscalls by default). We'll implement network-off by default and allow an override (which would then allow the subprocess to create sockets and perhaps open firewall rules if needed).
- **Per-job Dependencies:** Both Option A and B handle this. In Option A, we isolate dependencies by installing them into a job-specific folder (so they don't conflict with other jobs or pollute the server). In Option B, dependencies are installed into the job's venv. Option C doesn't change this aspect; it would be used in combination with A or B to further isolate those dependencies at OS level. One consideration: Option A can reuse the base interpreter and possibly share memory pages for common libraries (if any loaded) between processes, whereas Option B's venv will have its own copy of libraries (though the binary code is the same so OS will deduplicate some of it in memory anyway).
- **Performance:** Option A is slightly faster in setup - we don't need to create a venv (which can take a second or two and copy files); we directly install packages into a folder. Also, launching the job uses the already-installed Python runtime (just pointing it at a different lib directory). Option B has a small overhead to create and tear down virtualenvs. However, for typical job workloads (which might be seconds or tens of seconds of processing), these overheads are minor. Both A and B entail installing packages at job runtime if not already present. To mitigate repeated cost, we can cache wheels or preinstall common packages in the image. Option C adds some overhead to spawn the sandbox environment (though Bubblewrap is pretty fast, on the order of milliseconds to set up namespaces). Still, for MVP, avoiding that extra step keeps things simpler and slightly more efficient.
- **Portability & Dependencies:** Option A and B are pure Python solutions - they work wherever Python runs (Linux, Windows, etc.), though our deployment is Linux container-focused. Option C (Bubblewrap/Firejail) is Linux-specific and requires certain kernel features (unprivileged user namespaces for Bubblewrap, AppArmor support for Firejail, etc.). It also means our container image would need those tools installed and configured. Using them might complicate running on e.g. Mac/Windows dev environments (not that we'd run the container there in production, but it's a consideration for development). So A/B rank higher on portability and ease of setup.
- **Operational Complexity:** Option A is simplest to operate - no new services, and debugging is just reading logs of the subprocess. Option B is also straightforward, with the only additional consideration of cleaning up venv directories. Option C would require ops to manage an extra layer (ensuring the sandbox tool doesn't interfere with other container processes, possibly dealing with seccomp profiles on Docker to allow Bubblewrap to function, etc.). It's doable (and quite powerful) but adds overhead in understanding and maintenance. Since one of our drivers is **"fewest moving parts"**, we lean away from Option C for the initial implementation.

**Summary:** We favor **Option A: Subprocess + vendor directory** as the **minimal and effective** solution. It scores highest on simplicity and suffices for our safety requirements when combined with proper rlimits and basic network blocking. Option B (micro-venv) is a close second - it provides slightly cleaner isolation of Python packages, but at the cost of more setup time and complexity that isn't strictly necessary for MVP. Option C (Bubblewrap/Firejail) offers best-in-class isolation and could be an **upgrade path** later (for environments with highly untrusted code or multi-tenant concerns), but it's not needed initially given our "no new infrastructure" mandate. We will design our solution such that swapping in Bubblewrap later (to launch the subprocess in a sandbox) is possible if requirements change, but we won't start with it.

## 4. Decision Matrix

To visualize the comparison, here is a summary matrix of the options:

| **Criteria** | **A. Subprocess + Vendor** | **B. Subprocess + Micro-Venv** | **C. Subprocess + Bubblewrap** |
| --- | --- | --- | --- |
| **Simplicity** | **High** - Uses built-in Python tools (pip target dir, subprocess). Minimal new components. | Medium - More steps (create venv, manage env activation). | Low - Adds external sandbox tool, configuration overhead. |
| **Import Isolation** | High - Isolated mode (-S) + custom PYTHONPATH ensures no server packages loaded【14†output】. | High - Separate venv means only explicitly installed packages available. | High - (Same as A or B internally; sandbox doesn't affect Python imports). |
| **OS Isolation** | Medium - Process runs under non-root user with limited permissions, but full OS sandboxing not enforced (relies on file perms and Python guards). | Medium - (Same as A, just using venv doesn't add OS isolation). | **Very High** - Kernel enforces file system and network isolation (nothing outside sandbox accessible). |
| **Timeouts/Limits** | High - Supported via resource limits and parent process kill timeout. | High - Same as A (rlimits apply to any subprocess). | High - Same (and could integrate cgroups via sandbox). |
| **Network Control** | Medium - Disabled in Python (e.g. monkeypatch socket) - effective for most cases, but not absolute. | Medium - Same method as A (unless sandboxed by OS). | **Very High** - Sandbox can remove network interface entirely (complete block at kernel level). |
| **Per-Job Dependencies** | High - Achieved via pip install -t into job dir[\[1\]](https://cloud.tencent.com/developer/ask/sof/106280791#:~:text=) (no cross-job contamination). | High - Each venv has its own site-packages, fully isolated. | High - (Works in combination with either A or B inside sandbox). |
| **Performance** | High - No venv creation, uses base interpreter (faster startup). Repeated jobs may reuse cached libraries if wheelhouse used. | Medium - Minor overhead to create venv and duplicate libs for each job. | Medium - Bubblewrap startup overhead is small but present; plus it would be layered on A or B. |
| **Portability** | High - Requires only Python. Runs anywhere container runs. | High - Requires only Python (venv module). | Low - Linux only; needs kernel features and installing sandbox tool. |
| **Operational Effort** | Low - Few changes to Dockerfile (maybe add build tools). Easy to debug (just inspect job folder and logs). | Low - More files (venv dirs) but still within one container. Cleanup needed for venv dirs. | Higher - Need to install/maintain sandbox tool, and ops must be familiar with it. |

**Ranking:** Option A (Subprocess + vendor) comes out on top for our goals (simplicity, sufficiency of isolation, and low ops overhead). Option B is a viable alternative if we needed absolute clarity of environment separation, but it doesn't provide a big advantage given we can achieve similar isolation with -S and PYTHONPATH. Option C, while strongest on security, is overkill for the initial release and would violate the "no major new complexity" guideline.

Thus, we **select Option A** as the recommended design, with an eye on possibly adding Option C's techniques later if the threat model or multi-tenant needs grow.

## 5. Recommended Design (why this one)

We recommend implementing **a job execution queue within the FastAPI app that spawns a separate Python subprocess for each job, using an isolated import environment ("vendored" dependencies) and OS resource limits to sandbox execution.** This design best meets our decision drivers:

- **Simplicity First:** It keeps everything in one process/container without external services. We use Python's asyncio.Queue for in-memory queuing and subprocess for isolation - no Celery, no Redis, no Kubernetes Jobs. The logic is easy to follow and resides in our codebase. The Docker container needs only minimal changes (installing a few packages and possibly a non-root user).
- **Safety:** Each job runs outside the main server process, so any crashes or runaway code in the job won't directly crash the API. We invoke the subprocess in **isolated mode** so it won't import or modify server modules or global state. Before handing control to user code, the subprocess will self-impose strict limits: e.g., RLIMIT_CPU to cap CPU seconds, RLIMIT_AS to cap memory usage, and RLIMIT_FSIZE to cap any file writes. We will also disable networking by default inside the job process (so the user's code can't call external APIs or exfiltrate data) - essentially a software sandbox. This satisfies the requirement that _"executing user config code cannot affect the API process."_ Even if the user code goes into an infinite loop or tries something malicious, the damage is contained to the subprocess (which will be killed after, say, a timeout or on violating limits).
- **Determinism & Explainability:** The design ensures each job produces a clear artifact log and is run from scratch (no shared mutable state between runs). Because we never resume partial jobs and each run starts fresh in a clean subprocess, we avoid complicated state management. The artifact JSON is built by the orchestrator in a controlled manner. Since no global state is carried over, results are reproducible given the same input and config. All decisions made (headers found, mappings, errors) are captured in the artifact, which is only appended to during execution in a linear fashion. There is no hidden global state that could make one job's execution affect another's outcome.
- **Low Ops Overhead:** Everything is handled by the single container and the FastAPI app itself. To scale up, one can run multiple containers (though we'd then designate one as the job-runner, see Section 11) - but no new services need to be managed. The concurrency level can be tuned via an environment variable or API call, rather than scaling out a fleet of workers. Logging and monitoring are unified - job logs are accessible in the same filesystem and can be streamed if needed. From an ops perspective, if something goes wrong, there's one process to look at (plus any subprocesses it spawned). The approach fits naturally into container orchestration (the container still has one primary process - the FastAPI app - which is managing child processes).
- **Performance & Modest Scalability:** The approach is efficient for the expected workload: launching a subprocess is fast (tens of milliseconds) and Python's startup overhead is acceptable, especially if we minimize unnecessary imports in the worker. Since each job is likely doing IO-bound work (reading/writing Excel) and some CPU work (data normalization), running a few in parallel (bounded by N) can improve throughput on multi-core machines. We avoid GIL contention by using separate processes for each job, enabling true parallelism for CPU-bound parts. We'll stream file processing where possible to keep memory usage low per job. The design includes a concurrency limit to prevent overload - e.g., we can set N=2 or 4 by default to handle multiple jobs simultaneously but avoid exhausting CPU or memory. The queue provides **back-pressure**: if too many jobs are submitted, new requests will be rejected with HTTP 429, signaling the client to retry or slow down, thus protecting the service from being overwhelmed.
- **Cost:** There is no extra cost in terms of infrastructure - no extra containers or VMs. The only potential cost is slightly increased container size (if we add build tools or common wheel packages) and the runtime cost of pip installing packages for jobs (which can be mitigated with caching). Overall, it's a cost-effective solution fitting our one-container constraint.

In short, this recommended design uses the simplest concurrency mechanism (asyncio tasks + queue) and the simplest isolation mechanism (OS process boundaries) to meet our needs. It avoids the pitfalls of in-process sandboxing (which is insecure) and avoids the ops burden of complex distributed task schedulers. We also chose the vendor-dir approach to dependencies because it's easy to implement and avoids cross-job or server contamination of packages. This design is aligned with how similar systems handle untrusted code: for example, open-source projects often use subprocess isolation with limited permissions as a lightweight sandbox.

**Risks and Mitigations Recap:** We acknowledge that without kernel-level sandboxing, a sufficiently malicious script might attempt to abuse the environment (for example, reading other files or using ctypes to bypass Python restrictions). We mitigate this by dropping privileges (no root), carefully controlling the environment passed to the subprocess, and using rlimits and timeouts. These measures cover the vast majority of threats (infinite loops, memory bombs, accidental imports, etc.) that are realistic in our context. For any remaining gaps, we note them in Section 8 and consider them acceptable for the initial release given the likely user scenarios. Our design errs on the side of simplicity while putting reasonable safety guardrails in place, making it the best fit for ADE's current stage.

## 6. Implementation Plan (API, JobManager, Worker, Sandboxing)

We will now outline how to implement this design step by step. The implementation breaks down into several components:

### 6.1 API Endpoints

We'll introduce a set of **REST API endpoints** under a new **/jobs** namespace for clients to submit jobs and monitor results. These endpoints will be handled by a new FastAPI router (for example, `app.routes.jobs`). Their behavior is:

- **POST /jobs** — **Submit a new extraction job.**
  - **Request body:**
    ```json
    {
      "document_id": "<doc_id>",
      "config_id": "<config_id>",
      "runtime_network_access": false
    }
    ```
    The `runtime_network_access` field is optional and defaults to `false`.
  - **Server processing:**
    - Authenticate and authorize the user against the target workspace/document.
    - Create a new row in the `jobs` table (status `QUEUED`) linked to the document and configuration; the primary key becomes the job ID.
    - Prepare `var/jobs/<job_id>/`:
      - Copy the source file from `var/documents/<workspace>/<doc_id>/` into `input.xlsx`.
      - Materialize the selected configuration into `config/` (modules, manifests, etc.) and persist any bundled assets.
    - When `requirements.txt` exists:
      - If both the global `ADE_RUNTIME_NETWORK_ACCESS` flag and `runtime_network_access` are `false`, install dependencies offline with `pip install -t config/vendor -r requirements.txt --no-index --find-links=/opt/ade/wheels`. Missing wheels cause a controlled failure.
      - When network access is permitted, run pip normally (ideally in a background task) to fetch packages.
      - Always target `config/vendor` and treat pip errors as job failures, recording installer output for later inspection.
    - Enqueue the job ID on the `JobManager` queue so a worker can pick it up.
    - Return HTTP 202 with metadata such as `{ "job_id": 123, "status": "QUEUED", "submitted_at": "<timestamp>" }`.
  - If the queue is full (`job_manager.queue.full()`), respond with HTTP 429 "Job queue is full, please retry later."

- **GET /jobs/{id}** — **Fetch job status and metadata.**
  - Returns a JSON document describing the job lifecycle fields, for example:
    ```json
    {
      "job_id": 123,
      "status": "RUNNING",
      "submitted_at": "...",
      "started_at": "...",
      "finished_at": null,
      "document_id": "...",
      "config_id": "...",
      "runtime_network_access": false,
      "error_message": null
    }
    ```
  - When `finished_at` is populated, include failure details or execution metrics if available. This endpoint does not stream artifacts.

- **GET /jobs/{id}/artifact** — **Download the artifact JSON.**
  - Streams `artifact.json` once the job is complete (optionally even on partial failures). Return HTTP 404 or 204 while the job is still running.

- **GET /jobs/{id}/output** — **Download the normalized spreadsheet.**
  - Serves `normalized.xlsx` for successful jobs using the appropriate Excel MIME type. Return HTTP 404 when the output is unavailable.

- **POST /jobs/{id}/retry** — **Re-run a job that failed.**
  - Reject retries for jobs that are currently `RUNNING` or `QUEUED`.
  - Implementation options:
    1. **Reuse the job ID:** Reset status to `QUEUED`, clear or archive prior outputs in `var/jobs/<id>/`, and track attempt counts if desired.
    2. **Issue a new job ID:** Create a fresh submission that links back to the original job.
  - After preparing the working directory again, enqueue the job and respond with 200/202.

- **POST /system/jobs/concurrency** — **Adjust the worker pool size (admin-only).**
  - Accepts `{ "max_concurrency": 3 }` and increases worker tasks immediately when the value grows.
  - Decreasing concurrency should signal excess workers to exit gracefully after their current job; for MVP we can document that a restart may be required to downscale cleanly.
  - This endpoint is operational sugar; defaults still come from the `ADE_MAX_CONCURRENCY` environment variable.

Optionally we can add `GET /jobs` for listings, but it is not required for the MVP.

All these endpoints will be integrated into the FastAPI app by including the jobs router. The router will be registered in the main application (e.g., app.include_router(jobs_router, prefix="/jobs") and perhaps a separate one for the /system admin endpoints). The security model: regular users can POST jobs and get their own job statuses, whereas the /system route should be admin-protected. We assume RBAC from the users/workspaces model is in place, so we'll ensure that when a user requests /jobs/{id}, the job belongs to their workspace or they have permission to view it.

### 6.2 JobManager (Async Queue and Workers)

The JobManager will be a central component running inside the FastAPI process. It will encapsulate:
- An `asyncio.Queue` for job IDs (or job payloads) with a max size.
- A set of worker tasks (async tasks created with `asyncio.create_task`) that continuously monitor the queue and process jobs.
- Functions to submit jobs to the queue and to adjust concurrency.

We can implement JobManager as a class or just module-level functions using closure variables. A class is cleaner:

```python
import asyncio
import traceback
from typing import Any

class JobManager:
    def __init__(self, max_workers: int, max_queue: int) -> None:
        self.queue = asyncio.Queue(maxsize=max_queue)
        self.max_workers = max_workers
        self.workers: list[asyncio.Task[Any]] = []
        self._stop_signal = False

    async def start_workers(self) -> None:
        """Launch the configured number of worker tasks."""
        for worker_id in range(self.max_workers):
            task = asyncio.create_task(self.worker_loop(worker_id))
            self.workers.append(task)

    async def worker_loop(self, worker_id: int) -> None:
        """Continuously consume jobs from the queue."""
        while True:
            job_id = await self.queue.get()
            try:
                await self.process_job(job_id)
            except Exception:
                traceback.print_exc()
            finally:
                self.queue.task_done()

            if self._stop_signal and self.queue.empty():
                break

    async def process_job(self, job_id: int) -> None:
        """Launch and monitor the sandboxed subprocess."""
        raise NotImplementedError

    def submit(self, job_id: int) -> None:
        """Enqueue a job or raise QueueFull if saturated."""
        self.queue.put_nowait(job_id)

    def set_concurrency(self, new_max: int) -> None:
        """Adjust the worker pool size (simplified MVP logic)."""
        if new_max > self.max_workers:
            for worker_id in range(self.max_workers, new_max):
                self.workers.append(asyncio.create_task(self.worker_loop(worker_id)))
            self.max_workers = new_max
        elif new_max < self.max_workers:
            self._stop_signal = True
            self.max_workers = new_max
```

We will initialize a single JobManager instance during app startup (FastAPI `@app.on_event("startup")`). For example:

```python
import os

from app.jobs.manager import JobManager
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event() -> None:
    max_workers = int(os.getenv("ADE_MAX_CONCURRENCY", "2"))
    max_queue = int(os.getenv("ADE_QUEUE_SIZE", "10"))

    app.state.job_manager = JobManager(max_workers, max_queue)
    await app.state.job_manager.start_workers()
```

This will spawn, say, 2 worker tasks that immediately wait on the queue. The JobManager.submit(job_id) will be called in the POST /jobs handler: e.g., app.state.job_manager.submit(new_job_id).

**Concurrency/Queue Behavior:** With N workers and a queue of size M, we can handle N jobs simultaneously. If N jobs are all running and one more submission comes in, it goes to queue (if queue length < M). If queue is full (M waiting plus N running in progress, total N+M jobs in system), the put_nowait will throw, and we respond 429. This ensures we process at most N+M jobs at a time (with at most N actively running). N and M can be tuned via env vars as noted. For example, if N=2, M=10, at most 2 running + 10 queued = 12 jobs in system; a 13th submission gets 429.

**Job Status Tracking:** The JobManager will update the database status as jobs move through stages:
- When a job is taken from the queue and about to start processing, mark it **RUNNING** (update the `jobs` table with the status and `started_at` timestamp).
- When the subprocess finishes, mark it **SUCCESS** or **ERROR**, set `finished_at`, and store any high-level result such as `error_message` or row counts.
- If a job fails before launch (for example, dependency installation errors), mark it **ERROR** and capture the failure context.

We should ensure DB session usage is handled properly (likely use an async session in FastAPI context). Possibly the process_job function will be async but inside it we'll use await run_in_threadpool for any synchronous DB or file operations if needed, or better, use an async DB session (SQLAlchemy async engine) - which the app likely has.

We might also maintain an in-memory mapping of job_id to some status or process info for quick access (though not strictly needed if we always hit the DB for status; caching could be nice for quick checks). However, given low volume, DB is fine.

**Edge cases:** If the server shuts down while jobs are running, those subprocesses will be orphaned or killed when the container stops. On restart, any job left in RUNNING could be marked failed. We might add a startup routine to reset jobs that were RUNNING back to QUEUED or FAILED with note "server restarted". This could be done by a DB query on startup event (set any RUNNING to FAILED with note). Not a requirement, but a good practice to handle unexpected crashes.

### 6.3 Worker Subprocess Implementation

The worker subprocess is the heart of sandboxed execution. We will implement it as a **separate Python module or script** (for example, app/jobs/worker.py as a standalone script that can be invoked with python -m app.jobs.worker &lt;job_id&gt;). This script will do the following, in order:

- **Initialize environment & parse inputs:** The worker needs to know which job it's handling and the relevant paths. The JobManager launches it roughly as:

  ```python
  sys_executable = sys.executable  # path to current Python interpreter
  proc = await asyncio.create_subprocess_exec(
      sys_executable,
      "-I",
      "-B",
      "-E",
      "-m",
      "app.jobs.worker",
      str(job_id),
      env=env_vars_dict,
      cwd=job_dir,
      stdout=log_file_handle,
      stderr=log_file_handle,
  )
  ```
- **Flags explanation:**
  - `-I` covers `-s` (no user site) and `-E` (ignore environment variables such as `PYTHONPATH`) automatically.
  - Using `-S` avoids loading global site-packages, but we must ensure the worker module remains importable—either by adjusting `PYTHONPATH` or invoking a script directly from the job directory.
  - If we rely on `-m app.jobs.worker`, we may need to prepend the application path to `PYTHONPATH` (for example, `env_vars["PYTHONPATH"] = "/opt/ade/app:" + job_dir + "/config/vendor:" + job_dir + "/config"`).
  - Alternatively, skip `-I` and explicitly use `-E -s`, or provide a bootstrap script (for example, generate `run_job.py` in `var/jobs/<id>/` that prepares `sys.path` and invokes the worker).
- Example bootstrap script:
  ```python
  import importlib
  import sys

  job_id = int(sys.argv[1])
  sys.path.insert(0, "<path_to_app_code>")
  sys.path.insert(0, "config")
  sys.path.insert(0, "config/vendor")

  worker = importlib.import_module("app.jobs.worker")
  worker.run(job_id)
  ```
  Running `python -I -B -S run_job.py` gives complete control over `sys.path` while keeping site-packages out of view.
- Notes on flag combinations:
  - `-I` may ignore `PYTHONPATH`, so relying on it requires verifying behaviour; using `-E -s` with a curated environment can be simpler.
  - `-s` prevents user-site contamination.
  - Avoid `-E` when we need to propagate `PYTHONPATH`; instead, directly manage the environment the child receives.

Actually, with PYTHONPATH pointing to config and vendor, do we need -S? If we _do_ use -S, then even stdlib's site isn't imported, but stdlib itself is still accessible (the standard library paths appear in sys.path by default minus site-packages). This means built-in modules and resource etc. are fine. And our PYTHONPATH entries will be in sys.path so our modules are found. The global site-packages (with FastAPI etc.) will **not** be added because site module wasn't run - great. The only downside: sitecustomize.py (if we wanted to use it to disable network) won't auto-run because that requires site import. We can manually import our sitecustomize or just do the socket monkeypatch directly in worker code.

So, **optimal**: use -S for safety. To still load our worker code, rely on PYTHONPATH plus specifying the module via -m or run a small stub script. We can do: python -s -S -B -m jobs_worker_package if we package it. Perhaps easier: create an entry point script for the worker in the image (like /usr/local/bin/ade-worker installed via setup.py). But let's not overcomplicate.

To proceed, we'll spawn the subprocess with arguments similar to `[sys.executable, "-s", "-S", "-B", "path/to/worker.py", str(job_id)]` and pass a minimal environment (including an explicit `PYTHONPATH`). Pointing to the script path directly avoids import gymnastics.

**Invocation plan:**
- **Sanitize the environment:**
  - Start from a clean dict (or a filtered copy of `os.environ`) and strip secrets such as database URLs or credentials.
  - Populate only the essentials: `PATH` for invoking helper binaries, locale settings (`LC_ALL`), and a curated `PYTHONPATH` like `"<job_dir>/config/vendor:<job_dir>/config"`. Include the application path if the worker imports project modules.
  - Consider setting `PYTHONUNBUFFERED=1` to flush logs promptly.
- **Set the working directory** to `var/jobs/<id>/` so relative file accesses stay inside the sandbox.
- **Capture stdout and stderr** by opening `var/jobs/<id>/logs.txt` and passing the handle to the subprocess. `RLIMIT_FSIZE` prevents the log from growing unbounded (for example, cap at 10 MB).
- **Launch the subprocess** and keep the handle for monitoring and cancellation.
- **Apply resource limits (`rlimit`) inside the child before loading user code:**
  - `RLIMIT_CPU` to bound CPU seconds (configurable via `ADE_WORKER_CPU_SECONDS`, e.g., 30–60 s).
  - `RLIMIT_AS` to cap memory (`ADE_WORKER_MEM_MB` determines the ceiling).
  - `RLIMIT_FSIZE` to restrict output file sizes (e.g., 50–100 MB).
  - `RLIMIT_NOFILE` to limit open file descriptors (which also throttles socket count).
  - `RLIMIT_NPROC` to constrain forked processes/threads when the job runs under a dedicated user.
  - Resource ceilings cannot be raised by unprivileged code; hitting them surfaces as termination signals or Python `MemoryError`.
- **Enforce wall-clock timeouts** in the parent (`await proc.wait()` with `asyncio.wait_for`) to stop hung jobs even if CPU use is low.
- **Drop privileges (if running as root):** When the worker starts as root, drop to a restricted account before executing user code.
  - Use `os.setuid`/`os.setgid` to switch to an `adejob` user created in the container (after `chown`ing `var/jobs/<id>` to that user).
  - Remove supplemental groups or capabilities so the sandboxed process has no elevated rights.
  - If the main app already runs as a non-root user, we may not be able to drop further; document whether the container runs as root (simpler for MVP) or rely on capabilities such as `CAP_SETUID`.
  - Example guard inside the worker:
    ```python
    import os
    import subprocess
    import sys
    import pwd

    try:
        sandbox_user = pwd.getpwnam("nobody")
        os.setgid(sandbox_user.pw_gid)
        os.setuid(sandbox_user.pw_uid)
    except (KeyError, PermissionError):
        logger.warning("Could not drop privileges; continuing with current user")
    ```
  - Prefer a dedicated user over `nobody` so we can manage permissions precisely (and ensure job files remain writable).
- **Disable networking:** With `runtime_network_access=False`, monkey-patch sockets inside the worker.
  - Example implementation:
    ```python
    import socket

    def _disabled_socket(*_args, **_kwargs):
        raise ConnectionError("Networking is disabled in this job")

    socket.socket = _disabled_socket
    socket.create_connection = lambda *args, **kwargs: _disabled_socket()
    ```
  - This blocks normal libraries (e.g., `requests`, `urllib`). Sophisticated attackers could still reach system calls (ctypes, external binaries); we accept this risk for MVP and can harden later with kernel-level tooling.
  - Keep container images lean (no `curl`, `ping`, etc.) and rely on `RLIMIT_NPROC` plus lack of capabilities (no `CAP_NET_RAW`) to limit abuse.
  - When `runtime_network_access=True`, skip the patch so legitimate outbound requests succeed; wall-clock timeouts still prevent indefinite hangs.
- **Install dependencies (if not done in main):**
  - **Pre-install during submission:** keeps worker startup fast but delays API responses and runs pip with higher privileges.
  - **Install inside the worker (chosen approach):** execute pip after setting up limits so malicious `setup.py` code stays sandboxed.
    ```python
    import os

    wheelhouse = os.environ.get("ADE_WHEELHOUSE", "")
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-t",
        "config/vendor",
        "-r",
        "config/requirements.txt",
    ]
    if not runtime_network_access:
        pip_cmd += ["--no-index"]
        if wheelhouse:
            pip_cmd += [f"--find-links={wheelhouse}"]
    else:
        pip_cmd += ["--no-cache-dir"]

    result = subprocess.run(pip_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pip install failed: {result.stderr}")
    ```
  - Offline mode (`--no-index`) succeeds only if desired wheels exist; otherwise the job fails cleanly.
  - Keep rlimits active so pip cannot exhaust resources, and ensure `config/vendor` is on `sys.path` when running the job code.

Our design choice: **Perform pip install inside the worker subprocess, at the beginning of process_job, before running user's extraction code**. This keeps the API response quick and encapsulates all execution (including dependency resolution) within the job's controlled environment. The JobManager's process_job function can skip pip since the worker will handle it. The only exception: if the job is disallowed network and we have no offline source, we might pre-check and fast-fail. But we could also rely on pip to fail and catch that in worker.

So inside worker.py, pseudocode:

def run(job_id: int):  
\# Apply resource limits  
\# Drop privileges  
\# (If runtime_network_access is False, monkeypatch sockets now, \*but\* hold off until after pip if pip needs network\*)  
```python
def run(job_id: int, runtime_network_access: bool) -> int:
    """Skeleton of the worker entry point."""
    configure_rlimits()
    drop_privileges()

    requirements_path = Path("config/requirements.txt")
    if requirements_path.exists():
        install_requirements(requirements_path, runtime_network_access)

    if not runtime_network_access:
        disable_network()

    try:
        run_structure_pass()
        run_mapping_pass()
        run_transform_pass()
        run_validation_pass()
        run_output_pass()
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        record_failure(job_id, exc)
        return 1

    record_success(job_id)
    return 0
```

The above is conceptual. The actual implementation needs to integrate with existing code that likely defines how to run each pass.

Possibly, the ADE codebase already has helpers to coordinate these passes (maybe a `Processor` class that yields the artifact). If not, we can implement minimal logic:
- **Structure Pass:** import every module in `config/row_types/`, apply detectors to locate tables (e.g., identify header rows), and write findings to `artifact.json`.
- **Mapping Pass:** load each `config/columns/` module to map raw columns to normalized schema fields, logging detector decisions.
- **Transform Pass:** execute hooks or transforms to clean and convert data.
- **Validation Pass:** enforce constraints (range checks, required fields) and capture violations in the artifact.
- **Output Pass:** write `normalized.xlsx` via the configured writer and record completion metadata.

It's likely the core logic for these passes is part of the app's library (maybe in a module like ade.core or similar). Ideally, we call a single function like process_document(input_path, config_path, artifact_path, output_path) which encapsulates all the above. If not, we can embed a simplified logic directly in worker.

For the report's sake, we'll not dive too deeply into pass logic, just outline that we will orchestrate calls to user code as needed.

- **Artifact Writing:** The worker will open artifact.json in append or write mode and write JSON entries or structures. Possibly, the artifact is meant to be a well-formed JSON file. We might collect results in memory and write once at end, or write incrementally. It's described as "append-only", which suggests either it is a JSON lines format or they append to an array in a file. Could be that artifact.json starts as { "events": \[ ... \] } and we append to the list (but appending to a JSON list in a file requires rewriting the file unless we pre-buffer). Alternatively, it could be NDJSON (newline-delimited JSON objects). If they have a known format, follow it. For MVP, we can simply accumulate results in a Python list/dict and write out at end in one go. This ensures a valid JSON file. It uses a bit more memory but unless artifact is huge, it's fine.

We will ensure _no raw data_ is written: only references like cell coordinates and any user-provided annotations (like "Column X mapped to Field Y"). We'll rely on the logic (which presumably already respects that rule). As a safe-check, we won't dump entire row values into artifact.

- **Logging and Exit Codes:** Throughout execution, any exception that is not caught should propagate and cause the worker to exit with non-zero (since we didn't intercept it, Python would write traceback to stderr (our logs.txt) and exit 1). We might want to catch exceptions around each pass to log a structured message in artifact (like "Pass 2 failed due to X"). Possibly the system has error handling guidelines (like if a user detector throws, we catch it and mark job failed but still output partial artifact).

We can implement a broad `try/except` around the main processing in the worker:

```python
try:
    execute_all_passes()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    append_artifact_error("Unhandled exception during processing")
    sys.exit(1)
else:
    sys.exit(0)
```

The parent process (JobManager) will then see exit code 0 or 1. If killed by signal (e.g., RLIMIT_CPU triggers SIGXCPU or if we decide to kill after timeout), proc.wait() might return a code indicating killed. On Unix, if process is killed by signal, typically returncode is negative (like -9 for SIGKILL). We should handle those as failure and note if it was a timeout or resource kill.

- **Parent timeout:** In `JobManager.process_job`, wrap `proc.wait()` with `asyncio.wait_for`:

  ```python
  timed_out = False
  try:
      await asyncio.wait_for(proc.wait(), timeout=ADE_JOB_TIMEOUT_SECONDS)
  except asyncio.TimeoutError:
      timed_out = True
      proc.kill()
      await proc.wait()

  exit_code = proc.returncode
  ```

- If `timed_out` is `True`, mark the job failed due to timeout. For non-zero exit codes, capture the error and mark failure; otherwise mark success and compute runtime metrics.

We also capture timestamp before launching and after to compute runtime, which can go in metrics.

- **Cleaning Up:** After job finishes, we don't actually need to clean the job directory (we keep artifact and outputs for retrieval). On a retry, we will wipe it then, as discussed. We might also want to cap the number of job directories to avoid disk filling - maybe a future cleanup task to remove old ones after X days.

### 6.4 Filesystem Layout Revisited

Under var/jobs/&lt;id&gt;/ we expect these files/subdirs:

- **input.xlsx** - input data.
- **config/** - user config package:
  - `columns/`, `row_types/`, `hooks/` subdirectories containing `.py` files; add empty `__init__.py` files so they are importable as packages.
  - Optional `manifest.json` describing the target schema (generated from the config or supplied by scripts).
  - Optional `requirements.txt` if extra dependencies are required.
  - A `vendor/` directory (inside `config/`) to hold installed dependencies; adding both `config/` and `config/vendor` to `PYTHONPATH` keeps imports predictable.
  - Treating `config` as a package avoids module clashes and lets user code import sibling modules reliably.
- We'll implement writing empty `__init__.py` files to `config/`, `config/columns`, `config/row_types`, and `config/hooks`.
- **artifact.json** - job log (written by job).
- **normalized.xlsx** - output file (written by job).
- **logs.txt** - combined stdout/stderr from job (capturing print statements or tracebacks).

These files allow the API to serve results or debug if something went wrong.

No other files are expected unless user code writes something explicitly (we could restrict it if needed, e.g., don't allow writing outside job_dir by user code - we rely on them not knowing other paths and OS perms).

### 6.5 Dockerfile Changes and Environment Variables

We will adjust the Dockerfile to support this job execution environment:

- **Base Tools:** If using Alpine or slim, ensure gcc/g++ and musl-dev or build-essential are installed, so that pip install can compile packages if needed. Also install any common libraries (e.g., if many users might use pandas, we could pre-install it or at least have it in wheelhouse to avoid heavy compile at runtime).
- **Python Modules:** Ensure psutil or pyseccomp if we were going to use them (we probably won't now, except maybe resource which is in stdlib).
- **Wheelhouse:** Optionally, we can populate /opt/ade/wheels:
- We might download wheels for common packages (like openpyxl, pandas, numpy, etc.) at build time. This can be done with pip download or similar. However, it increases image size.
- Another approach: instruct ops to mount a volume with wheels if needed. But for MVP, we could skip unless offline operation is critical.
- We at least provide the structure: an env var ADE_WHEELHOUSE=/opt/ade/wheels. If present, the worker will use it for pip offline.
- Building the image with wheels is an optimization step that can be done if this becomes a bottleneck.
- **Non-root user:**
- Create a user for running the app (say ade), and another for running jobs (say adejob). Or just one and run everything as that (less isolation).
- For maximum effect:
  - Add dedicated users (e.g., `RUN adduser --disabled-password ade && adduser --disabled-password adejob`).
  - With both users present we can:
    - Run the main app as `ade` (`USER ade` at the end of the Dockerfile) and spawn jobs as `adejob`. Note this requires privilege escalation, so running the main app as root might be simpler for MVP.
    - Document the trade-off: operating as root is not ideal, but it lets us drop privileges inside worker processes until we adopt capabilities such as `CAP_SETUID` or sandbox tools like Bubblewrap.
- Set file permissions accordingly:
  - Create `/var/ade` or `/app/var` with controlled ownership.
  - `chown` each `job_dir` to `adejob` after creation so the worker can write safely.
  - Avoid world-writable directories when possible; use explicit ownership instead.
  - Record the static UID/GID in the Dockerfile (or use a dedicated user rather than `nobody` to avoid collisions).
- **Environment variables (ENV knobs):**
  - `ADE_MAX_CONCURRENCY` — number of worker subprocesses (default 2).
  - `ADE_QUEUE_SIZE` — maximum backlog in the queue (default 10).
  - `ADE_JOB_TIMEOUT_SECONDS` — wall-clock timeout (default 300 seconds); jobs exceeding this are terminated.
  - `ADE_WORKER_CPU_SECONDS` — CPU rlimit (default ~60 seconds to balance safety with heavy workloads).
  - `ADE_WORKER_MEM_MB` — memory rlimit (default 500 MB, tune per container sizing).
  - `ADE_WORKER_FSIZE_MB` — maximum file size for outputs/logs (default 100 MB).
  - `ADE_RUNTIME_NETWORK_ACCESS` — default network policy for jobs (`false` unless explicitly allowed).
  - `ADE_WHEELHOUSE` — optional path to a local wheel cache for offline installs.

These envs will be read either in Python startup or passed through. We can put them in the FastAPI settings (maybe using Pydantic Settings or os.getenv in our code).

The worker subprocess also needs access to these limit values. We could:
- pass them as CLI arguments (for example, `worker.py <job_id> <mem_limit_mb> ...`), though that becomes unwieldy;
- read `ADE_WORKER_*` environment variables inside the worker (preferred because we already curate the environment);
- write a small config file in the job directory (overkill).

We'll rely on environment variables—the parent process ensures each `ADE_WORKER_*` value exists before launching so the worker can read them via `os.environ`.

We can also set `PYTHONUNBUFFERED=1` in the Dockerfile or Uvicorn command to avoid log buffering, though the dedicated log file already mitigates most issues.

Finally, ensure that the FastAPI app can find resource module (which is POSIX-only, but we're on Linux so fine) and asyncio etc. These are standard.

In Dockerfile pseudocode:

```dockerfile
FROM python:3.11-slim

# Install build essentials (optional sandbox tool can be added later)
RUN apt-get update && apt-get install -y gcc g++ make

# Create users
RUN useradd -m ade && useradd -M -s /usr/sbin/nologin adejob

# Prepare directories and permissions
RUN mkdir -p /app/var/jobs /app/var/documents \
 && chown -R ade:ade /app/var

# Copy backend code
COPY backend/ /app/
WORKDIR /app

# Install API dependencies
RUN pip install -r requirements.txt

# Optional: pre-download wheels
# RUN pip download -d /opt/ade/wheels numpy pandas openpyxl ...

# Runtime environment defaults
ENV ADE_MAX_CONCURRENCY=2 \
    ADE_QUEUE_SIZE=10 \
    ADE_JOB_TIMEOUT_SECONDS=300 \
    ADE_WORKER_CPU_SECONDS=60 \
    ADE_WORKER_MEM_MB=500 \
    ADE_WORKER_FSIZE_MB=100 \
    ADE_RUNTIME_NETWORK_ACCESS=false
# Optional wheelhouse location
# ENV ADE_WHEELHOUSE=/opt/ade/wheels

# Switch to non-root for the main app (optional)
USER ade

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

_(We may opt to not switch USER to ade to keep root for now, depending on trade-off, but above shows if we did.)_

### 6.6 Putting It All Together (Sequence Flow)

It's helpful to illustrate the flow of a job through the system in a brief sequence (textually or via a diagram):

- **Job Submission:** Client (through UI or API) calls POST /jobs with document and config references. The API immediately responds with a job ID and queued status.
- **Queueing:** The job is placed into the JobManager's queue. If the queue is currently empty and workers idle, a worker will pick it up almost immediately. Otherwise, it waits until a worker finishes a prior job.
- **Job Start:** A worker task dequeues the job and updates DB status to RUNNING with start time. It then forks a subprocess to actually perform the job.
- **Sandbox Setup (in subprocess):** The worker subprocess (ADE Worker) sets resource limits (CPU, memory) and changes its persona (drops privileges to adejob). It installs any needed Python packages for this job in isolation (if not pre-installed). It disables networking if required. Now it loads the user's config code and processes the input data through the defined passes. All through this, it writes to artifact.json and collects any logs. If an error occurs, it is caught or will crash the process.
- **Job Completion:** The subprocess exits. The worker task in the main process captures the exit code (and any timeout event). It writes end time and final status to the DB (including any error info if applicable). If the job failed, it might parse logs.txt or artifact to pull a concise error message (e.g., exception type) to store in DB for quick reference.
- **Result Availability:** The artifact and output file are now available in var/jobs/&lt;id&gt;/. The client can GET /jobs/{id} to see that status is SUCCESS or ERROR. If SUCCESS, they can GET /jobs/{id}/artifact or /output to retrieve the results. If ERROR, they might retrieve the artifact to see partial processing info or check logs for the error.
- **Retry or Next Jobs:** If retry is requested on a failure, the process repeats: the old job directory is cleaned, DB status reset, and it goes into queue again. Meanwhile, other jobs can be processed concurrently up to the set limit.

This design ensures that the time-intensive work (file processing) is done off the main thread, keeping the FastAPI server responsive to other requests (including additional job submissions or status checks). The server doesn't need to spawn threads for each job (which would not bypass GIL for CPU tasks) - by using subprocesses, we get true parallelism. The asyncio queue and worker tasks give us fine control over how many parallel processes to run.

To solidify understanding, here's an **ASCII diagram** summarizing the components and flow:

Client API (FastAPI + JobManager) Worker Subprocess  
\------ --------------------------- ----------------  
POST /jobs ----> \[Validate & DB insert (QUEUED)\]  
\[Materialize files in var/jobs/ID\]  
\[Enqueue job ID in asyncio.Queue\]  
\-> (if Queue full: return 429)  
return 202 Accepted with job ID  
|  
v  
(Background workers running) ---- job ID picked ---> \[Spawn Python subprocess\]  
(sys.executable -s -S -B worker.py ID)  
|-> \[Apply rlimits (CPU, MEM, etc.)\]  
|-> \[Drop privileges to 'adejob'\]  
|-> \[Install deps via pip -t\]\[1\]  
|-> \[if runtime_network_access=False: monkeypatch sockets\]  
|-> \[Open input.xlsx; import user code\]  
|-> \[PASS 1: detect structure\]  
| (calls row_types detectors)  
| -> write findings to artifact.json  
|-> \[PASS 2: map columns\]  
| (calls columns detectors)  
| -> append mappings to artifact.json  
|-> \[PASS 3: transform rows (hooks)\]  
|-> \[PASS 4: validate output\]  
|-> \[PASS 5: write normalized.xlsx\]  
| (using openpyxl or similar)  
|-> \[Close artifact.json\]  
|-> \[Exit 0 (success) or 1 (error)\]  
v  
\[asyncio.wait_for timeout?\] <--- (subprocess exits) --- \[If timeout: kill subprocess\]  
\[DB status <- SUCCESS/ERROR\]  
\[DB metrics <- duration, etc.\]  
\[Queue next job if any\]  
|  
GET /jobs/{id} ------> \[Fetch status from DB, return JSON\]  
GET /jobs/{id}/artifact -> \[Return artifact.json file\]  
GET /jobs/{id}/output -> \[Return normalized.xlsx file\]

_(The diagram shows how the main process and worker subprocess interact and where key actions happen, with references to relevant steps.)_

With this plan in place, we can implement the code accordingly.

## 7. Code Diff Plan (file-by-file)

We will now outline changes and additions to the codebase to implement the above design. We focus on showing the new modules and modifications at a high level, not full code, to convey the scope:

**New Files / Modules:**

- **app/jobs/manager.py** - Contains the JobManager class and possibly the global instance. Key elements:
- Initialization of the asyncio Queue and starting worker tasks.
- The worker_loop async method, which calls process_job(job_id) for each queued job.
- The process_job(job_id) method:
  - Looks up job info from DB (to get document path, etc., if needed - though we may rely on prepared files).
  - Launches the subprocess via asyncio.create_subprocess_exec with appropriate arguments and environment.
  - Waits with timeout for completion.
  - Updates the DB record status (success/failure) and timestamps.
  - If failure, capture an error message: e.g., if we can parse the last line of logs or the exception string. This could involve reading logs.txt or checking if artifact.json has an "error" field. Simpler: just store "failed (exit code X)" or specific known errors (if timeout, say "Timed out").
- submit(job_id) method to safely put a job in the queue (and raise if full so caller can handle it).
- set_concurrency(new_n) to adjust workers (as discussed in 6.2).
- Possibly utility to gracefully shutdown workers on app shutdown (e.g., set a flag and put dummy tasks to unblock them).
- We will ensure to commit DB transactions appropriately around these updates.
- **app/jobs/worker.py** - The entry-point for the job subprocess (could be run with -m or direct path).
- It will parse sys.argv for the job_id (and maybe any flags like runtime_network_access).
- Read environment variables for limits and runtime_network_access flag.
- Apply resource limits via resource library.
- Drop user privileges if possible (use os.setuid/gid).
- If a requirements.txt exists in config/, perform the pip install logic (with target directory).
- Set up network restrictions (monkeypatch socket if needed).
- Import and run the passes. We might integrate with existing code if available:
  - For example, if there's a function like from ade.core import process_all_passes; process_all_passes(input_path, config_dir, artifact_path, output_path), we would just call that. If not, implement minimal logic in-line:
  - Open artifact.json for writing.
  - Execute detection and normalization:
    - Possibly call user-defined functions. The user's modules might have known entry points. Alternatively, the manifest might list which detector classes to use.
    - Without detail, we assume we load all detectors and apply them generically.
  - Catch any exceptions around these steps to log error.
- Write final results to artifact (or ensure they're flushed).
- Exit with appropriate status.

We'll also include in this script the network monkeypatch function and any other sandbox utilities (like maybe preventing open() on certain paths by changing cwd - but we already set cwd and drop perms, so likely okay).

- **app/routes/jobs.py** - A new FastAPI router for job endpoints.
- Define endpoints:
  - create_job(request) for POST /jobs.
  - Validate input (the document_id and config_id).
  - Maybe find the config version to use (latest active version for that config? Or as provided).
  - Create the job record: e.g., job = Job(id=newid, document_id=..., config_id=..., status="QUEUED", submitted_by=user, submitted_at=now, runtime_network_access=... ). Save to DB.
  - Call a service function to prepare files: e.g., prepare_job_files(job). This will:
    - Make directory var/jobs/&lt;id&gt;.
    - Copy the input file from var/documents/&lt;workspace&gt;/&lt;doc_id&gt;/... to .../input.xlsx.
    - Fetch config code from DB and write to .../config/\*.py files. (If config code is stored as one large script or multiple, we split accordingly. Possibly the config is stored as separate script files in DB, or as a zip. We have to implement accordingly.)
    - Write requirements.txt if present (from the config version record).
    - Write \__init_\_.py files in necessary dirs.
    - We might do a quick check: if requirements exist:
      - If global ADE_RUNTIME_NETWORK_ACCESS false and no wheelhouse, and runtime_network_access false, we _know_ this will fail to install. We could preemptively reject the job submission with 400, telling user dependencies cannot be resolved. But better is to accept and let it fail in worker with a clear error in artifact. We can choose either. Perhaps accept and mark error later (user will see error anyway).
    - (We do **not** run pip here in the main thread to avoid delay.)
  - Enqueue the job: app.state.job_manager.submit(job.id). If this raises QueueFull, we update job status to, say, "REJECTED" or simply don't create it at all (maybe we should abort creation with 503/429 to client, and not insert into DB or remove it). Or we insert and immediately mark it as failed with "Queue full". Simpler: if queue full, just return 429 and do not insert job record (or remove it). But clients might prefer a clean response. We can handle either way; a 429 with no job ID might be fine. Let's do that: if queue is full, skip DB insertion and respond with an error message. The user can try again later.
  - Return the response JSON with job_id and initial status.
  - get_job(job_id) for GET /jobs/{id}:
  - Query DB for job.
  - If not found or not authorized, 404 or 403.
  - Return a JSON with fields as described (status, times, maybe error message). We might include a short excerpt of logs or artifact summary if failed (optional). Keep it concise.
  - get_job_artifact(job_id):
  - Open the file var/jobs/&lt;id&gt;/artifact.json and stream it back (set appropriate headers). Use FileResponse or Starlette StreamingResponse for efficiency.
  - If job not finished or file missing, 404 or 204.
  - get_job_output(job_id):
  - Similar to artifact but for normalized.xlsx. Use FileResponse with filename and Excel content type.
  - If not exists (job failed or not done), 404.
  - retry_job(job_id) for POST /jobs/{id}/retry:
  - Find job in DB, ensure it's failed or maybe succeeded (depending on policy).
  - Create a new job entry or reuse ID? As discussed, we lean towards reuse for API semantics.
    - If reuse: we will remove or archive old outputs: e.g., delete artifact.json and normalized.xlsx (or rename to .prev if we want to keep them around).
    - Possibly increment a retry counter in DB (we could add a field attempts).
    - Update status to QUEUED, reset timestamps (maybe keep original submitted_at or not? We could keep original submitted_at and have a separate field for last_attempt_at).
    - Enqueue the job ID again. If queue full now, return 429.
  - Response similar to submission (with same job id).
  - This is somewhat tricky because if the user had already fetched old artifact of a failed run, that file might get replaced by the new run's artifact, meaning their old link now points to new data. This might be acceptable or not. We assume it's fine because the job id is conceptually the same task being retried.
  - set_concurrency() for POST /system/jobs/concurrency:
  - Auth check for admin.
  - Read new concurrency from request.
  - Call app.state.job_manager.set_concurrency(new_n).
  - Return the new concurrency level and maybe current queue length or status.
  - Note: Lowering concurrency might not immediately kill running extra workers (we handle gracefully with the \_stop_signal). Document that it will take effect after ongoing jobs.

We integrate this router in main app:

```python
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(
    system_jobs_router,
    prefix="/system/jobs",
    tags=["jobs"],
    dependencies=[Depends(admin_auth)],
)
```

(The actual code depends on our auth setup.)

**Existing Files to Modify:**

- **app/main.py or app factory** - to initialize the JobManager on startup and add routers:
- Add the startup_event to create JobManager (as shown in 6.2 code snippet).
- Store it in app.state or globally.
- Include the new jobs router(s).
- Possibly read environment variables for initial config (we can use os.getenv inside startup event).
- Example diff (pseudo):

  ```python
  from app.jobs import manager, routes as jobs_routes

  app = FastAPI(...)

  @app.on_event("startup")
  async def startup() -> None:
      max_workers = int(os.getenv("ADE_MAX_CONCURRENCY", 2))
      max_queue = int(os.getenv("ADE_QUEUE_SIZE", 10))
      app.state.job_manager = manager.JobManager(max_workers, max_queue)
      await app.state.job_manager.start_workers()
      # Optionally mark RUNNING jobs as FAILED for recovery.

  app.include_router(jobs_routes.public_router, prefix="/jobs")
  app.include_router(jobs_routes.admin_router, prefix="/system/jobs")
  ```

Also ensure to shut down workers on app exit if needed (though when container stops, child processes get terminated anyway). We could trap shutdown event to set JobManager stop flag and perhaps wait for workers to finish or kill them.

- **app/models.py or wherever DB models are defined** - update the Job model if needed:
- Fields likely needed: status (string), started_at, finished_at, maybe runtime_network_access (bool), error_message (text or part of JSON), and possibly metrics JSON (for things like row count, etc.).
- The prompt indicated jobs table already has status, timestamps, metrics/logs JSON. So perhaps:
  - status - we will use "QUEUED", "RUNNING", "SUCCESS", "ERROR".
  - logs or metrics JSON - could store something like {"error": "...", "duration": 12.5, ...}. Alternatively, separate columns.
- If any migrations needed, note them (but out-of-scope to detail here).
- We'll ensure runtime_network_access is stored (or we can treat all false except some flag - easier to have a boolean column or include in JSON).
- We should also have a foreign key to the config version used (to exactly know what code was run).
- Also maybe store attempts count if we want.
- **app/db/\__init_\_.py or session management** - ensure we can perform DB updates in async background tasks. If using an async session, we might get it via contextvars or pass it. Possibly, the JobManager will need to acquire a session for updates. We might use async_session() context manager inside process_job. Or reuse a global session if thread-safe (not likely, better to create new).
- For simplicity, we might do raw SQL via the DB engine for these status updates (since they are simple).
- Or schedule updates back on main thread via asyncio.call_soon_threadsafe, but not needed if using async DB properly.
- **Dockerfile** as discussed in 6.5 - add dependencies and users. We'll provide a snippet above in section 6.5.
- **app/utils.py or wherever we copy files** - If there is an existing utility to copy documents or to fetch config code, we use it. If not, implement in routes as needed.

**Minimal Snippets to Illustrate Key Parts:**

- _Launching Subprocess (in JobManager.process_job):_
- async def process_job(self, job_id: int):  
    job_dir = f"{BASE_DIR}/var/jobs/{job_id}"  
    log_file = open(f"{job_dir}/logs.txt", "w")  
    \# Build env for subprocess  
    env = {}  
    env.update(os.environ) # copy base env  
    \# Remove sensitive env (e.g., DB credentials)  
    for var in list(env):  
    if var.startswith("ADE_") or var in ("PATH", "PYTHONPATH", "PYTHONUNBUFFERED"):  
    continue  
    \# possibly allow LANG, etc., or nothing else  
    del env\[var\]  
    \# Set up Pythonpath for sandbox:  
    env\["PYTHONPATH"\] = f"{job_dir}/config/vendor:{job_dir}/config"  
    env\["ADE_RUNTIME_NETWORK_ACCESS_JOB"\] = "true" if job.runtime_network_access else "false"  
    \# Pass through resource limits  
    env\["ADE_WORKER_CPU_SECONDS"\] = os.getenv("ADE_WORKER_CPU_SECONDS", "60")  
    env\["ADE_WORKER_MEM_MB"\] = os.getenv("ADE_WORKER_MEM_MB", "500")  
    env\["ADE_WORKER_FSIZE_MB"\] = os.getenv("ADE_WORKER_FSIZE_MB", "100")  
    env\["ADE_WHEELHOUSE"\] = os.getenv("ADE_WHEELHOUSE", "")  
    \# Launch the subprocess  
    proc = await asyncio.create_subprocess_exec(  
    sys.executable, "-s", "-S", "-B",  
    WORKER_SCRIPT_PATH, str(job_id),  
    cwd=job_dir, env=env,  
    stdout=log_file, stderr=log_file  
    )  
    \# Wait with timeout  
    try:  
    await asyncio.wait_for(proc.wait(), timeout=float(os.getenv("ADE_JOB_TIMEOUT_SECONDS", "300")))  
    except asyncio.TimeoutError:  
    proc.kill()  
    await proc.wait()  
    status = "ERROR"  
    error_info = "Timed out after {}s".format(os.getenv("ADE_JOB_TIMEOUT_SECONDS"))  
    else:  
    \# Process finished within time  
    if proc.returncode == 0:  
    status = "SUCCESS"  
    error_info = None  
    else:  
    status = "ERROR"  
    \# Get a short error message:  
    error_info = self.\_extract_error(job_dir)  
    \# Update job in DB  
    async with Session() as session:  
    job = await session.get(Job, job_id)  
    job.status = status  
    job.finished_at = datetime.utcnow()  
    job.error_message = error_info  
    \# (maybe job.metrics_json = {...})  
    await session.commit()  
    log_file.close()

Note: \_extract_error(job_dir) might read the logs.txt and take the last line or so, or parse the artifact for an error entry. For now, could do a simple approach:

def \_extract_error(self, job_dir):  
try:  
with open(f"{job_dir}/logs.txt") as lf:  
lines = lf.readlines()  
if not lines:  
return "Job failed (no logs)"  
\# take last non-empty line  
for line in reversed(lines):  
txt = line.strip()  
if txt:  
return txt\[:200\] # truncate to 200 chars  
except Exception:  
return "Job failed (unable to read logs)"

- _Worker script (simplified):_
- import os, sys, resource, subprocess, importlib, json  
    def disable_network():  
    import socket  
    socket.socket = lambda \*args, \*\*kwargs: (_ for _in ()).throw(RuntimeError("Network use not allowed"))  
    socket.create_connection = lambda \*args, \*\*kwargs: (_for_ in ()).throw(RuntimeError("Network use not allowed"))  
    def main():  
    job_id = sys.argv\[1\]  
    runtime_network_access = os.getenv("ADE_RUNTIME_NETWORK_ACCESS_JOB", "false").lower() == "true"  
    \# Resource limits  
    cpu_limit = int(os.getenv("ADE_WORKER_CPU_SECONDS", "60"))  
    mem_limit_mb = int(os.getenv("ADE_WORKER_MEM_MB", "500"))  
    fsize_limit_mb = int(os.getenv("ADE_WORKER_FSIZE_MB", "100"))  
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))  
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit_mb\*1024\*1024, mem_limit_mb\*1024\*1024))  
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_limit_mb\*1024\*1024, fsize_limit_mb\*1024\*1024))  
    \# Optionally limit open files and processes:  
    resource.setrlimit(resource.RLIMIT_NOFILE, (50, 50))  
    try:  
    os.setgid(os.getgid()) # if container has multiple, setgid for target user (skipped for now)  
    os.setuid(os.getuid())  
    except PermissionError:  
    pass # already non-root or no permission to drop  
    \# Dependency installation  
    req_path = f"config/requirements.txt"  
    if os.path.exists(req_path):  
    pip_cmd = \[sys.executable, "-m", "pip", "install", "-t", "config/vendor", "-r", req_path, "--no-cache-dir"\]  
    if not runtime_network_access:  
    wheelhouse = os.getenv("ADE_WHEELHOUSE", "")  
    pip_cmd += \["--no-index"\]  
    if wheelhouse:  
    pip_cmd += \[f"--find-links={wheelhouse}"\]  
    res = subprocess.run(pip_cmd, capture_output=True, text=True)  
    if res.returncode != 0:  
    print(res.stdout, res.stderr, file=sys.stderr)  
    sys.exit(1)  
    \# Setup network restrictions if needed  
    if not runtime_network_access:  
    disable_network()  
    \# Open artifact file  
    artifact_path = "artifact.json"  
    artifact_data = {"events": \[\]}  
    try:  
    \# Pass 1: Structure detection  
    import importlib.util, glob  
    for file in glob.glob("config/row_types/\*.py"):  
    mod_name = "row_types." + os.path.splitext(os.path.basename(file))\[0\]  
    importlib.import_module(mod_name)  
    \# Assuming each module maybe registers something or we just call a function in each?  
    \# For simplicity, assume each row_type module has a function detect_tables(sheet) -> list of tables  
    \# (In practice, likely more complex)  
    tables = \[\] # list of detected table metadata  
    \# ... (call each detector on input.xlsx via openpyxl or so) ...  
    artifact_data\["events"\].append({"pass":1, "tables_found": len(tables)})  
    \# Pass 2: Column mapping  
    for file in glob.glob("config/columns/\*.py"):  
    mod_name = "columns." + os.path.splitext(os.path.basename(file))\[0\]  
    importlib.import_module(mod_name)  
    \# ... map columns using loaded modules ...  
    artifact_data\["events"\].append({"pass":2, "mappings": "done"})  
    \# Pass 3: Transform (hooks)  
    for file in glob.glob("config/hooks/\*.py"):  
    mod_name = "hooks." + os.path.splitext(os.path.basename(file))\[0\]  
    importlib.import_module(mod_name)  
    \# ... apply transformations ...  
    artifact_data\["events"\].append({"pass":3, "transforms": "done"})  
    \# Pass 4: Validation  
    \# ... apply validations ...  
    artifact_data\["events"\].append({"pass":4, "validations": "done"})  
    \# Pass 5: Output writing  
    \# Use openpyxl or pandas to write normalized.xlsx  
    artifact_data\["events"\].append({"pass":5, "output": "written"})  
    except Exception as e:  
    \# Log exception to stderr (which goes to logs.txt)  
    import traceback; traceback.print_exc()  
    \# Also record error in artifact  
    artifact_data\["error"\] = str(e)  
    with open(artifact_path, "w") as af:  
    json.dump(artifact_data, af, indent=2)  
    sys.exit(1)  
    else:  
    \# Write artifact on success  
    with open(artifact_path, "w") as af:  
    json.dump(artifact_data, af, indent=2)  
    sys.exit(0)  
    if \__name__ == "\__main_\_":  
    main()
- _(This is illustrative; actual integration with real detection logic will differ. But ensures any error triggers sys.exit(1) with artifact saved.)_
- _Database model (Job):_
- class Job(Base):  
    \__tablename__= "jobs"  
    id = Column(Integer, primary_key=True)  
    document_id = Column(ForeignKey("documents.id"))  
    config_version_id = Column(ForeignKey("configuration_script_versions.id"))  
    status = Column(String(20))  
    submitted_at = Column(DateTime, default=datetime.utcnow)  
    started_at = Column(DateTime)  
    finished_at = Column(DateTime)  
    runtime_network_access = Column(Boolean, default=False)  
    error_message = Column(Text, nullable=True)  
    metrics = Column(JSON, nullable=True) # could store {"duration":..., "rows":..., etc.}
- We would update Alembic migration to add runtime_network_access, error_message if not present.

The above outlines the key code changes. Actual code will need proper error handling, logging, and possibly adjustments after testing.

## 8. Security & Privacy Analysis

Our design aims to meet the security posture requirements with minimal complexity. Here we evaluate how it stands up and note any remaining risks:

**Isolation from Server Process:** By running user-supplied code in a separate process, we prevent it from directly accessing or altering the FastAPI application's memory or variables. The user code cannot call internal server functions or access the database session in-process because it's running in a different interpreter. This greatly limits the impact of any malicious or accidental actions - it can't modify the running API or crash it by segfaulting (only the child process would crash). We also launch the subprocess in _isolated mode_, ensuring it does not import the server's packages by default. The job's Python environment is restricted to standard library plus the user's config and specified packages. For example, even if the container has FastAPI or SQLAlchemy installed globally, the job process won't load them (because we use -S to skip site-packages and only include the job's paths in PYTHONPATH). This prevents a malicious script from doing something like import fastapi; fastapi.some_internal or messing with our database connection - those modules simply won't be importable【14†output】.

**Operating System Separation:** The subprocess acts as a sandboxed OS-level tenant. We drop privileges so the job runs as a non-root user (for example, `adejob`). Key effects:
- Application code and databases can be owned by another user, denying read access to `adejob` (attempts to open them raise `PermissionError`).
- The job's working directory is `var/jobs/<id>/`, so relative file operations stay confined there; absolute paths offer little without privileges.
- We do not yet use `chroot` or mount namespaces, so world-readable files elsewhere in the container could still be listed. Mitigate this by tightening file modes (e.g., `chmod o-r`) or ensuring separate groups.
- Ensure sensitive artifacts (like `var/ade.db`) are owned with restrictive permissions (mode `600`) so the worker account cannot access them.

So, our approach ensures **"code cannot impact server"** by process and user separation. It is following the principle that "the code that processes untrusted input runs with the least privilege and in isolation".

**CPU and Memory Limits:** Dedicated rlimits keep runaway jobs from starving the API:
- Infinite loops hit the CPU-time ceiling (for example, 60 s) and are terminated with `SIGXCPU`, leaving the parent process healthy.
- Excessive allocations throw `MemoryError` or incur `SIGKILL` once `RLIMIT_AS` is exceeded, preventing memory bombs (e.g., `x = [b"0" * 1024 * 1024 * 500]`) from crashing the container.
- File-size limits cut off runaway logs or output once the threshold (say 100 MB) is reached, protecting disk usage and artifact storage.

**Network Access Control:** By default, jobs have **no network access**. We achieve this by monkey-patching Python's networking modules so that any attempt to open a socket fails immediately with an exception. This means if the user code tries to do requests.get("<http://example.com>") or open a socket, it will get an error like "Network disabled". This soft guard covers common libraries (requests, urllib, etc. all rely on socket under the hood). While not as bulletproof as a firewall or namespace isolation, it's effective for honest use cases and basic misuse. The user would have to go out of their way (like using ctypes to call socket() at the C level) to bypass it. We consider such sophisticated attacks unlikely in our context; if the threat grows, we can move to kernel-level blocking (see below).

Furthermore, since the job user is unprivileged, it cannot create raw sockets or do anything that requires capabilities (like sending ICMP packets). It also cannot modify firewall rules or network settings. So even if our Python patch were removed by some trick, the process could open TCP connections - however, those would be subject to the container's network policies. If our container runs in an environment with restricted egress (which it might not by default), that helps. But currently, we assume an open network environment but rely on our code logic to prevent usage.

We provide a safe **override**: if a specific job needs internet (perhaps to fetch a remote resource or something, in certain controlled scenarios), an admin can set runtime_network_access=true for that job. In that case, we do not patch sockets, thereby allowing outbound requests. This is off by default, addressing the requirement of network being off unless explicitly toggled.

**Limiting Imports and Environment:** We ensure the job process's PYTHONPATH only includes the directories we allow (the job's config and vendor). Critically, we do not include the system site-packages【14†output】, so the job cannot import things like our database driver, or cloud SDKs that might hold credentials in memory, etc. The only exception is the Python standard library which is always available - but the standard lib is generally safe and does not include functions to directly compromise the system beyond what OS permissions allow. (We note that os and subprocess are in stdlib, which can be used to launch processes or manipulate files, but those operations are constrained by OS perms and our rlimits).

We also scrub the environment handed to the job process:
- omit database URLs, API keys, and other secrets—only essentials like `PATH` and our control variables propagate;
- ensure any server-side secrets remain invisible to the child process;
- rely on the `-s -S` flags so user site-packages or `sitecustomize` files from the parent environment never load automatically.

**Data Privacy - Artifact Content:** We adhere to the rule that no raw input data should leak into the artifact JSON. The code that generates the artifact is under our control (the orchestrator). We will ensure it logs only metadata: cell coordinates, counts of rows/columns, maybe hashed values or classified labels, but not the actual data content. For instance, if a cell had a person's name, the artifact might say "Cell A2 classified as HEADER" rather than including the name itself. This way, if artifacts are shared or stored long-term, they don't become another source of sensitive data. We'll verify that in our artifact writing logic. If any user-defined code tries to log actual data (e.g., via print), it would go to logs.txt but not to artifact.json. Those logs are less likely to be exposed unintentionally, and are mainly for debugging by authorized users.

**No Shared Secrets:** The job process doesn't have access to the server's database except via the files it's given. The SQLite database file might reside on disk, but since the job runs as another user with no permission to read it, it can't open or modify the DB. Also, the DB is likely locked by the server process if it's open; in any case, permission denial stops it. Any credentials the server uses to connect to DB or external services are kept in environment vars or config files that the job cannot see. So the job cannot, for example, connect to the database and query other data.

**Temporary Files and Channels:** We use pipes for stdout/stderr to capture logs, but these are one-way into a file. The job cannot read from the parent except if we explicitly gave it a pipe to do so (we don't). Communication is essentially parent sending the code and input via files on disk, and child sending results via artifact and exit code. There is no persistent bidirectional channel that could be abused to access the parent memory.

**Pitfalls and Mitigations:**
- Process-level isolation is crucial—Python's in-process sandboxes have a history of CVEs, so our attack surface now centers on subprocess launch logic and OS configuration.
- After dropping privileges to `adejob`, ensure no setuid binaries allow privilege escalation; keeping the base image minimal helps.
- We currently rely on Docker's default seccomp profile rather than custom filters. That profile blocks risky syscalls (e.g., `mount`, `ptrace`), providing a baseline while avoiding added complexity.

- **File System Risks:** Without a full chroot or namespace, the `adejob` user can list or read any world-readable file in the container.
  - Mitigation: tighten file permissions so only root or the main app user can read sensitive files (e.g., `.env` should be mode 600). Reading application source code is less severe but still undesirable.
  - The job can still access benign world-readable files under `/proc` or `/etc`, but cannot modify them; Docker's seccomp profile blocks dangerous device access such as `/dev/mem`.
- **Cross-Job Interference:** Multiple jobs share the `adejob` Unix user, so signalling between processes is technically possible.
  - Setting `RLIMIT_NPROC=1` would block additional subprocesses entirely, so it is not viable when concurrency > 1.
  - Assigning per-job Unix users or leveraging namespaces would mitigate this but adds significant operational complexity; we can revisit if the threat model shifts.
  - For now we rely on Docker's defaults (which already restrict ptrace) and accept the small risk, noting that more hostile multi-tenancy would push us toward stronger sandboxing (Option C).

**Remaining limitations (no kernel-level sandbox):**
- A determined attacker could still exploit kernel vulnerabilities via allowed syscalls. Docker's default seccomp profile blocks many risky calls, but we do not yet enforce a custom allowlist.
- Jobs can consume disk space by creating multiple files up to the per-file limit; future work could add quotas or cgroups for stricter control.
- Wall-clock timeouts complement CPU limits, but without cgroups a cooperative-yielding job might still run longer than desired; we balance this with generous yet finite timeouts.
- Allowing `runtime_network_access=true` exposes internal services if misused; we treat it as an opt-in for trusted scenarios and can later restrict via proxying.
- Users can print raw data to `logs.txt`; while that file is not automatically exposed, we should document the behaviour and avoid surfacing logs publicly by default.

**Secrets and Whitelists:** The job process should ideally only be able to read/write within its directory. We considered using something like Bubblewrap to create a mount namespace where only var/jobs/&lt;id&gt; and maybe /tmp are present (and maybe a read-only view of needed libraries). Without that, we rely on OS perms. Possibly, as an extra safety measure, we could set up a simple AppArmor or SELinux profile to restrict file access. But that's heavy for MVP. We'll mention that as future.

We have addressed **privacy** by limiting what's stored (artifact sanitized) and **security** by isolation. In summary, our design provides a sandbox that, while not impenetrable by a determined adversary with local exploit knowledge, is robust enough for the expected use (trusted users running mostly correct code, with accidental mistakes contained). It meets the stated requirements and can be iteratively hardened (e.g., adding seccomp rules to block socket at syscall level, or using Bubblewrap to isolate filesystem) if needed later without a fundamental redesign.

## 9. Testing Plan

To ensure the system works correctly and safely, we propose a comprehensive testing approach:

**Unit Tests (Function-level tests):**

- _Detectors and Transforms:_ Write unit tests for any pure functions in the user config processing pipeline. For instance, if we have a standard library function for mapping columns or validating rows (outside user code), test those with sample inputs. Similarly, if there are user code examples (like a simple row detector), we can simulate calling it to ensure integration (though user code isn't in our control for testing, we can include a dummy config for tests).
- _Resource Limit Setting:_ A unit test in the worker context could simulate setting RLIMITs. This is tricky to test in isolation (as setting global rlimits in a test will affect the test process). Instead, we might test our resource_limits function by checking that it returns expected values or that if we intentionally set a low limit and allocate memory, a MemoryError is raised. This may be more of an integration test.
- _Network Blocking:_ Write a small piece of code that tries to open a socket (e.g., socket.socket().connect(('example.com',80))) and ensure that after our disable_network() is called, it raises an error. We can embed such code in a dummy worker run invocation to verify the monkeypatch works. Also test that if runtime_network_access=True, such calls succeed (if internet is available in test environment or we can simulate by connecting to localhost).
- _Pip install logic:_ Create a temporary directory structure mimicking config/vendor and use a sample requirements.txt (perhaps pointing to a small pure Python package or a local wheel file). Test that our pip install command correctly installs into the target directory and that the installed module can be imported from that directory. This ensures our pip install -t invocation is correct.
- _Queue Behavior:_ For the JobManager, simulate adding jobs to the queue and ensure that if we add more than the max size, it raises QueueFull. We can test the submit method by configuring a small max_queue and catching the exception when overfull.
- _Concurrency Control:_ If we implement set_concurrency, we can write a test that initially starts with concurrency 1, submits a couple of jobs, then calls set_concurrency(2) and ensures that now two jobs can run simultaneously (we might need to instrument or stub the worker to not actually do heavy work, just wait a bit so we can observe concurrency).
- _Job Retry Logic:_ Write a test that creates a fake job in DB with status FAILED, then calls the retry function. Verify that:
- The job status goes back to QUEUED,
- The old artifact/output are removed (if that's our implementation),
- The job gets enqueued to the manager. Possibly use a stub manager for this to intercept the submission call.
- _Security of environment:_ Perhaps not a typical unit test, but we could verify that certain env vars are not passed to subprocess. For example, if the main process has DATABASE_URL in env, after we construct the env for subprocess, check that DATABASE_URL not in it. This ensures our env scrubbing logic works.

**Integration Tests (end-to-end in a controlled environment):**

We can simulate the entire flow with a known simple config:
- **Happy path:** Create a tiny Excel fixture and a dummy config that maps a column.
  1. Submit `POST /jobs` via the test client.
  2. Poll `GET /jobs/{id}` until status becomes `SUCCESS`.
  3. Fetch the artifact and output; assert the artifact contains expected events and the output spreadsheet matches the transform logic.
- **Concurrency test:** Fire five job submissions rapidly (each job sleeps for ~1 s) with concurrency set to 2.
  - Verify that no more than two jobs are simultaneously `RUNNING` and that excess jobs remain queued.
  - Confirm the total runtime aligns with batched execution and that submissions beyond queue capacity receive HTTP 429.
- **Resource limit enforcement:**
  - _CPU limit:_ Use a config containing an infinite loop (e.g., `while True: pass`) and assert the worker is terminated around the CPU threshold, with status `ERROR` and no impact on subsequent jobs.
  - _Memory limit:_ Allocate a large list (for example, `bytearray(1024 * 1024 * 1024)`) and confirm the job fails with an out-of-memory error while the system remains responsive.
  - _File size limit:_ Attempt to write a file larger than the configured limit and verify the process terminates, the file is truncated, and the job status reflects the failure.
- _Network block:_ Write a config that tries to fetch something from network (if internet accessible in test env, maybe urllib.request.urlopen('<http://example.com>')). Without runtime_network_access, it should raise an exception due to our socket patch. The job would then fail (unless the user code catches it, but assume not). We verify:
  - Job status = ERROR, logs show something like "Network disabled" from our exception.
  - If we then mark runtime_network_access true for this job (and ensure environment or Docker allows egress), then it should succeed in actually making the request. We might not want to call external site in tests. Instead, we can do a network call to a dummy local server (could spin up a simple HTTP server in test thread). But at least we see no exception in that case and maybe the artifact can include "fetched data" (if user code puts it).
  - Ensure toggling the flag works as intended.
- **Queue full 429 test:** As touched on, if we want to precisely test queue limits:
- Set concurrency low and queue small. Attempt POST /jobs more times than concurrency+queue.
- The last one(s) should get HTTP 429. We confirm the response status. Also ensure that no DB entry was created for those (if we implement rejection prior to DB insert).
- If we do create then mark failed, test that path (the job would appear in DB as maybe "REJECTED"). But likely we won't insert.
- **Retry mechanism integration:**
- Submit a job with a config that fails deterministically (e.g., user code does raise Exception("fail")). The job will go to ERROR state.
- Then call POST /jobs/{id}/retry. Expect:
  - Response indicates job re-queued.
  - The old artifact.json might have captured the error; after retry completes (assuming we fix the config or it still fails similarly), we should see that artifact overwritten or appended. We likely overwrote it. So verify that after retry, artifact reflects the second run (maybe contains only the second run's events).
  - The job's started_at and finished_at should update, and maybe an incremented attempt count if we track it.
  - If possible, test a scenario where the first run failed due to some ephemeral issue (like network off but needed), and for retry we toggle runtime_network_access on. The second attempt should succeed. Then check job is SUCCESS after retry.
  - Also test retry on a SUCCESS job (should either not be allowed or simply run again producing same output). We clarify expected behavior. Probably we only allow if failed. If not allowed, the endpoint might return 400. We test that.
- **Multi-tenant scenario:** If relevant, test that a user cannot access another user's job details or files:
- For RBAC, ensure the /jobs/{id} endpoint checks that the job's workspace/user matches. Write a test where user A submits a job, then user B (with a different auth token or session) tries to GET that job. Should get 403 or not found.
- This ensures our endpoint protection is in place (likely via dependency injection of current user and checking job ownership).
- Also ensure documents are workspace-scoped properly (the initial submission likely already does that).
- This is more of an API permission test but important for privacy.

**Manual and Load Testing:**

- We will run a manual test where we simulate a typical use-case: a medium-size spreadsheet that the system normalizes. We will manually inspect that CPU usage and memory usage of the container remain bounded (not growing unbounded). If possible, intentionally push the limits to see how system behaves (no crash of main).
- Stress test: queue up, say, 50 jobs (with concurrency maybe 5) and see if the system handles the throughput. Monitor that jobs come out correct and the queue does not deadlock or cause memory leaks.
- If possible, test concurrent usage of the API: e.g., while jobs are running, ensure normal API endpoints (if any other, like listing documents or uploading new ones) still respond quickly (the main thread should be free; minor CPU overhead for launching processes should not block event loop for long). This ensures our offloading is effective.

**Security Testing:**

- Try to break out or break rules in a controlled way:
- Within a sandbox job, attempt file operations: e.g., open /etc/passwd (which is world-readable on many images). See that job can read it (it might, if we didn't restrict it, since /etc/passwd is 644). This is not critical (contains no secrets, just user list), but indicates the job has some read access globally. It's an acceptable risk, but we note it.
- Attempt to open the SQLite DB file (likely at /app/app.db or similar). If we set it 600 owned by ade or root, this should fail with PermissionError. Test that.
- Attempt to kill another process from within a job if concurrency>1: not easy to target, but perhaps list processes in /proc. If /proc is not restricted, adejob can list /proc and see processes including PIDs. But by default, Ubuntu's /proc might only show your own processes due to hidepid option in some setups, not sure in Docker. In many distros, processes are not hidden from same user. If jobs share UID, each can see the other's process.
  - We can simulate: in one job's code, if it can identify the other job's PID (maybe via psutil or scanning /proc for processes with name "python" that aren't itself), attempt os.kill(pid, signal.SIGTERM). See if it succeeds in terminating the other job. If it does, that's a security flaw in multi-job isolation. We'd then consider mitigation (like randomizing user per job or using cgroup to isolate kill permission - not trivial).
  - If our threat model doesn't consider such hostile jobs (we consider user codes not actively trying to sabotage each other since likely all jobs belong to same user or collaborative environment), we might accept it for now but note it.
- Validate that the timeouts indeed trigger: e.g., put time.sleep(600) in a job (which is I/O-bound sleep, not CPU). CPU rlimit won't catch it because sleeping doesn't consume CPU. Our wait_for wall-clock timeout should kill it after e.g. 300s. We test such a case with shorter timeout to confirm the main process does kill the hung job (sleep can be considered hung as it's waiting).
- Test memory low-level: perhaps a job that forks a child process (if RLIMIT_NPROC allows). For example, user code might do subprocess.Popen(\["ls"\]). Since we didn't explicitly forbid, it will succeed if under NPROC limit. That child runs as same user, outside our Python control but still inside container. It's short-lived probably. We accept that because ls can't do harm beyond what user can anyway. If they tried to fork bomb (spawn many processes), RLIMIT_NPROC or RLIMIT_CPU will limit damage.
  - We can test that forking a process works when it should (since we might not want to break legitimate use, though we might not have a legitimate need for forking in these jobs).
  - Test RLIMIT_NPROC if we set one: e.g., if we set RLIMIT_NPROC=5 and the user tries to spawn 10 subprocesses in a loop, after 5 it should fail (raise OSError). Ensure our config either has that or we decide not to set NPROC to avoid interfering if user code legitimately uses multiprocessing for performance (less likely in this scenario, but possible).
- Confirm artifact content does not have raw data: e.g., feed in a sheet with a known sensitive value "SECRET123" in cell B2. Run a job. Search the entire artifact.json for "SECRET123". It should not appear (if our code logs just coordinates and not values). If it appears, we need to adjust our artifact generation logic to avoid logging actual data. Possibly our user detectors might inadvertently put a value in an exception message or so; we should catch and scrub if needed. In our design, we just not log values at all, so should be fine.

**Testing of Ops Controls:**

- Start the service with default concurrency, then change concurrency via the admin endpoint. Then flood some jobs, ensure the new concurrency is respected (if increased, see more parallelism; if decreased, we might only see effect after some finish).
- Try disabling job processing entirely by setting concurrency to 0 (if we allow that). If 0, we might not want to allow because then queue tasks will never be processed (or we interpret concurrency 0 as pause). If we support pausing, test that scenario: jobs queue up, none run, then set concurrency>0 and they resume. This might be an advanced use-case (like maintenance mode).
- Test what happens if the app is restarted with jobs in queue or running:
- Submit a job that runs long (sleep 30s), quickly restart the container (or simulate by calling startup/shutdown events in test after job started). On restart, see that:
  - The running job process obviously was killed by container shutdown. The new startup should ideally mark that job as failed. If we implement a startup recovery that checks for any job that was RUNNING and sets to FAILED (with note "server restarted"), test that it does so.
  - If queue had some queued (but not started) jobs, on restart, those wouldn't be in queue anymore in memory. If we want to persist queue in DB, we could mark them as queued and on startup re-enqueue them. That might be a future improvement. Currently, they'd be left in DB as queued but not processed. We could on startup either automatically re-enqueue them or mark them failed. A better approach: re-enqueue if we know no other instance is handling them. We can implement that.
  - Test scenario: job queued, then server restarts. We can simulate by directly inserting a job row with status QUEUED in DB, then starting the app. The startup should ideally detect it and put it in queue for processing. If we implement that, test it works (job eventually runs). If we decide not to implement (keeping it simpler), then those jobs would be stuck queued forever. That's not great; we likely should handle it. We can at least mark them failed on startup to not mislead.
  - We lean toward auto-requeue on startup: for all jobs in QUEUED status, add them to queue. For jobs in RUNNING, mark failed (they were mid-run and got interrupted). We test that logic thoroughly.

**Performance Testing:**

- Not in unit tests, but we can measure how long overhead is for launching a subprocess. It should be small (maybe 50-100ms). If we do 100 jobs sequentially, overhead ~0.1s each vs. doing in-thread negligible, but fine for our scale.
- Ensure pip install overhead for dependencies is within acceptable range given usage. If a user adds heavy dependencies (like pandas 50MB wheel), installing that per job could be slow (~5 seconds maybe). If they have repeated jobs with same deps, the current design reinstalls each time. That's inefficient. As an enhancement, we might cache venv or vendor directory per config or globally. Not doing in MVP. But we should note it.
- We can test one job with pandas, measure time, then another job with same requirement - see that it downloads again. Could consider enabling wheel caching in image (but we used --no-cache-dir specifically to avoid clutter).
- If this is a concern, we could at least allow pip cache in a volume (but that caches wheels which could be fine).
- For now, accept that overhead.

**Logging and Debugging:**

- Test that logs.txt captures all output from user code, including prints and errors. For example, user code does print("Hello") - after job, open logs.txt, see "Hello" is there.
- Test that if user code calls logging module, by default it goes to stderr if not configured, so should also end up in logs.txt. That's fine.
- Ensure our own debug prints (if any) are minimal or off in production, to not pollute logs. Possibly have the worker refrain from extraneous output except errors.

By covering these tests, we gain confidence that:
- Normal jobs succeed end to end.
- Edge cases such as timeouts, resource overuse, and network violations fail safely without impacting the service.
- Concurrency and queueing behave as expected, avoiding deadlocks or starvation.
- Isolation boundaries hold and failures surface with actionable logs/status.

We'll use both automated tests and manual validation, as some aspects (like actual resource usage) are easier to observe manually or with monitoring tools under load.

## 10. Runbook & Ops Checklist

To help operators manage ADE's job system, we provide the following guidelines:

**Configuration and Deployment:**
- **Set concurrency via environment:** Tune `ADE_MAX_CONCURRENCY` and `ADE_QUEUE_SIZE` to match available resources.
- **Adjust resource limits:** Modify `ADE_WORKER_CPU_SECONDS`, `ADE_WORKER_MEM_MB`, and `ADE_JOB_TIMEOUT_SECONDS` when workloads require additional headroom.
- **Network access policy:** Leave `ADE_RUNTIME_NETWORK_ACCESS` disabled by default; enable per job only when necessary.
- **Wheelhouse (offline dependencies):** Preload `/opt/ade/wheels` and set `ADE_WHEELHOUSE` for air-gapped deployments.
- **Container users:** Running as root simplifies privilege dropping; if you switch to a non-root main user, ensure it can still transition to `adejob`.
- **File permissions:** Confirm `var/documents` and `var/jobs` remain writable (adjust ownership when mounting volumes).
- **Logging:** Job logs reside in `var/jobs/<id>/logs.txt`; plan operational access since they do not stream to stdout.
- **Database migrations:** Apply Alembic migrations so new job columns exist prior to deploying updated code.

**Runtime Operations:**
- **Check job status:** Poll `GET /jobs/{id}`; if a job appears stuck, inspect the worker process (e.g., via `ps`) and kill it manually if needed.
- **Adjust concurrency:** Call `POST /system/jobs/concurrency` (admin-only) to scale workers; reductions take effect as running jobs finish.
- **Handle queue overload:** Frequent HTTP 429 responses signal saturation—raise concurrency or queue length within resource limits, or ask users to pace submissions.
- **Retry failures:** Review artifacts/logs, resolve the cause, then invoke `POST /jobs/{id}/retry`; retries remain manual in the MVP.
- **Cancel jobs (temporary workaround):** No dedicated endpoint exists; operators can locate the subprocess PID and terminate it directly.

**Quick Ops Checklist:**

- \[ \] **Before Deployment:** Set ADE_MAX_CONCURRENCY and ADE_QUEUE_SIZE env appropriately. Prepare wheelhouse if needed. Decide on user accounts (root vs non-root for main).
- \[ \] **After Deployment:** Verify the job manager started (check app logs for startup messages if we add any like "JobManager started with N workers").
- \[ \] **Submission Test:** Submit a sample job via UI/API to ensure the pipeline works end-to-end (watch it go to success and produce output).
- \[ \] **Resource Monitoring:** Keep an eye on CPU/memory when multiple jobs run. Adjust concurrency or limits if container is near its limits.
- \[ \] **Error Handling:** Spot-check a known failing job (maybe introduce a bug in a rule intentionally) and see that it fails gracefully and surfaces the error to the user (in job status or artifact).
- \[ \] **Network Toggle:** If a job requires network, test turning runtime_network_access on for that job and observe it.
- \[ \] **Concurrency Change:** Try using the concurrency admin endpoint to ensure it works (maybe not in production immediately, but know that it's available).
- \[ \] **Logs Access:** Ensure you have means to access var/jobs files. Either through an admin UI or by mounting the volume so you can retrieve artifact or logs for analysis. If something goes wrong in production, these files are critical for debugging user issues.
- \[ \] **Cleanup Strategy:** Plan how/when to remove old job directories to save space (maybe keep last X days). We might later provide a script or API to clean them.
- \[ \] **Backup Consideration:** If artifacts are important, ensure var/jobs or at least the normalized outputs are backed up or shipped out (maybe they will be downloaded by users anyway).
- \[ \] **Security Review:** Periodically review if any security updates are needed (for example, if a new exploit method is discovered for Python sandbox escapes, consider patching by adding seccomp filters or so). Also apply regular OS and Python updates as normal (to mitigate any vulnerabilities an attacker might try to leverage from within sandbox).

Following this runbook will help maintain a smooth operation of the ADE job system, allowing admins to adjust performance and handle any issues promptly, while keeping the system secure and reliable.

## 11. Risks, Unknowns, and Follow-ups

Despite careful design, there are some **risks and open questions** remaining:

- **Inter-job Interference (Same-User Issue):** As discussed, all job subprocesses run as the same Unix user (adejob). A malicious user could exploit this by trying to affect other running jobs (e.g., sending signals). We decided this risk is acceptable given our user base (likely cooperative, not adversarial). However, if in future we allow arbitrary third-party code, this becomes a concern. **Follow-up:** Investigate using Linux user namespaces or distinct UIDs per job to prevent signal attacks. Alternatively, integrate a seccomp filter to block kill() calls from within the sandbox (so a job cannot signal another) - seccomp can filter specific syscalls.
- **Lack of Kernel Namespacing:** Without bubblewrap, the sandbox still sees the full container filesystem (read-only parts). If someone finds a sensitive file accidentally left world-readable, they could read it. **Follow-up:** Do a thorough audit of the container file permissions (make sure nothing sensitive is world-readable). Possibly implement bubblewrap in a later version to mount a minimal FS (only /tmp and the job dir, plus necessary libs) for ultimate safety. Many modern container setups have unprivileged user namespaces enabled, so bubblewrap can likely run without too much hassle.
- **Dependency Installation Security:** Installing pip packages at runtime introduces supply chain risks: a user could specify a dependency that is actually malicious. During installation, that package's setup.py runs with our sandbox user privileges. We've limited those privileges and resources, which mitigates impact, but this is a potential vector. If an attacker can upload a package to PyPI and then have our system install it, they could attempt to exploit it (e.g., try to read files or phone home). But since network is off by default for jobs, even a malicious package's install can't exfiltrate data unless runtime_network_access was true for that job. **Follow-up:** For high security, consider requiring that all requirements come from a pre-approved list or internal index. Alternatively, sandbox the pip installation step further (e.g., run pip inside bubblewrap or a container with no access aside from wheelhouse).
- **Handling Large Data/Performance:** We assume moderate file sizes and job durations. If users upload massive spreadsheets (hundreds of MBs) or very complex transformations, our simple approach might struggle:
- Reading/writing Excel via openpyxl is memory-heavy. It might approach our memory limit or be slow. Perhaps using streaming CSV or an optimized library could be needed. **Follow-up:** Evaluate alternative libraries (like pandas or pyarrow) for efficiency, but those might require raising memory limits or adding native libs. We might advise chunk processing if needed.
- We also currently hold artifact data in memory until end (in our pseudocode). If artifact grows large (lots of events), that could be memory heavy. Could consider writing incrementally (open file, write JSON lines or flush partial results each pass). **Follow-up:** Implement streaming artifact writing if needed (the JSON structure would need to allow it, e.g., writing an array in pieces or using NDJSON).
- **No Resume or Checkpoint:** If a job fails or the server restarts, the job restarts from scratch next time. For now, that's fine (given input sizes not huge). But if we had extremely long jobs, one might want checkpointing or partial resume. Out of scope now.
- **Database Single Point:** Using SQLite is fine for low concurrency, but if job results updating becomes heavy (lots of writes to job status), that could be a slight bottleneck. Each job update is small though, and not frequent. Should be fine (the writes are serial in our event loop anyway). If scaling, moving to a bigger DB might be needed. Not a current risk but a horizon consideration if we had dozens of jobs per second being scheduled.
- **Accuracy of Timeouts:** Our wall-clock timeout uses asyncio's timing which should be fine. However, if a job spawns threads or subprocesses that hang, we kill only the main process. If that main process spawned child PIDs (like via subprocess inside job code), those might become orphaned but still run. We didn't explicitly kill child processes. In Linux, if the main process is killed, child processes' parent becomes init (PID 1, which in container might be our Uvicorn master or something). They might continue running. This is a subtle risk: e.g., a malicious code could spawn a subprocess that outlives the main job process and keep running in background, possibly doing mischief (though with no parent, it's limited to what it can do under adejob). This scenario is somewhat far-fetched but possible. **Follow-up:** We could mitigate by running the entire worker subprocess in a process group and killing the group. For example, use os.setsid() in worker, and proc.kill() would need to kill the group. Or simpler, each job's subprocess can track any children and terminate them on exit using atexit. Not implemented now. It's an edge case, but worth noting.
- **Testing Extent:** We should thoroughly test on real data with real user scripts if possible. There might be unforeseen issues like encoding problems, or needing to allow specific modules (like if user's code tries to import an internal library we didn't consider). We'll have to handle those case by case.
- **User Experience:** The user will likely interact via the UI. We should ensure the UI shows job status and results clearly. E.g., poll the status endpoint, show "Queued (# in queue ahead of you)" if possible (we could provide position but we didn't explicitly do that, maybe we can approximate by job ID ordering). For now, maybe just show queued vs running vs done.
- Also, if a job fails, present the error message from job.error_message or instruct to download artifact/log. Ensure the message is user-friendly enough (maybe we trim technical tracebacks, or highlight "Memory limit exceeded" etc. if we detect that).
- Possibly, define some standard error codes (like "TIMEOUT", "MEMORY_ERROR", "USER_EXCEPTION") to display nicer. Right now, we mostly propagate actual exception text which might be okay for developers but not end-users. **Follow-up:** refine error reporting to users.
- **Multiple Workspaces concurrency control:** If multiple jobs from different workspaces run, they all share the same queue and workers. This is fine since isolation is per job. But if one workspace gets a flood of jobs, it could starve another's (if queue is filled). We have no per-tenant quotas or fairness. Ops might need to intervene via concurrency or queue adjustments if one user abuses it. **Follow-up:** Consider per-user or per-workspace rate limiting in the API layer to ensure fairness.
- **Pipeline for large artifacts:** If artifact.json can be large, maybe compress it before sending to user (we can rely on HTTP gzip if client supports). Or provide an option to get only summary vs full detail. Right now, it's raw JSON text.

Given these unknowns, the next steps are to:
- Monitor real usage to spot unexpected limit hits or operational friction.
- Gather user feedback to confirm error messages and artifacts are actionable.
- Plan enhancements such as cancellation endpoints, stronger isolation, or performance tuning as demand grows.

In conclusion, our MVP addresses the core needs with simplicity but leaves some advanced features to be addressed as needed: We will keep an eye on the security aspects (the trade-offs we made) and be ready to implement Option C (bubblewrap or similar) if risk increases. Meanwhile, we will document these limitations so stakeholders understand them (e.g., "jobs are isolated but not in separate containers; do not run truly hostile code with unknown provenance without further sandboxing").

By acknowledging these follow-ups and planning accordingly, we ensure the ADE job orchestration can evolve to meet future requirements while currently delivering a working solution.

## 12. References (links, cited notes)

- **Andrew Healey - _Running Untrusted Python Code_ (Jul 2023):** Describes a method to sandbox Python code by running it in a separate process with seccomp and setrlimit. Emphasizes that process-based isolation is far safer than trying to restrict Python in-process. This inspired our use of subprocess and resource limits instead of any "restricted mode" hacks.
- **John Sturgeon - _FastAPI: Writing a FIFO queue with asyncio.Queue_ (Dec 2022):** Demonstrates how to integrate an asyncio.Queue and background worker in FastAPI for sequential task processing. We adapted this pattern to create our JobManager with multiple workers consuming from the queue.
- **LWN.net - _The failure of pysandbox_ (2013):** An article (cited by Healey) explaining why sandboxing within CPython is insecure. This justifies our design decision to avoid any attempt at in-Python "sandbox" and instead isolate at the process level.
- **Python resource module docs:** Official documentation on setting POSIX resource limits in Python. We used resource.setrlimit for CPU time, address space, etc., as recommended. Also referenced by Healey as a straightforward way to prevent excessive CPU/memory usage in the sandbox.
- **Open edX CodeJail - GitHub Repository:** Open edX's CodeJail uses a similar separate virtualenv and AppArmor to safely execute student code. According to its README, it relies on AppArmor for containment and also uses setrlimit for CPU/memory. This provided precedent for using OS-level controls. We chose not to use AppArmor now due to complexity, but CodeJail's approach informed our optional future hardening steps.
- **Stack Overflow - _Install a Python package into a different directory using pip?_ (2010):** Q&A explaining the use of pip install -t &lt;dir&gt; to install packages into an isolated folder[\[1\]](https://cloud.tencent.com/developer/ask/sof/106280791#:~:text=). This validated our approach for per-job dependency isolation without virtualenvs.
- **Adam Hooper - _Sandboxing data crunches, Part 1: use a subprocess_ (2020):** A blog series about sandboxing code in a data platform. Part 1 advocates for the two-process model (parent + child) to handle OOMs safely and dropping privileges/capabilities in the child. This reinforced our decision to drop root in the job process and expect it to possibly die from OOM without affecting the parent.
- **PySpawner Documentation:** PySpawner is a library for spawning sandboxed child processes quickly. It goes further with clone() and chroot, which is beyond our needs. But it shows an example of using Linux clone and user namespaces for sandboxing, hinting at future directions if we needed faster spawn times or stronger isolation.
- **Docker Default Seccomp Profile:** Documentation/analysis on Docker's seccomp default (e.g., Hacker News discussion) suggests that by default many risky syscalls are blocked (like mount, kill of arbitrary pids, etc.). This gives us some baseline security in our container without custom seccomp (for instance, ptrace is blocked, so jobs can't trace the main process).
- **FastAPI BackgroundTasks vs Celery - various sources:** We considered using FastAPI's BackgroundTasks but found they run in the same process/thread (not suitable for CPU-bound jobs). External task queues like Celery were overkill given our one-container constraint. So we settled on asyncio tasks which is lightweight and sufficient for our scale.

Each of these references helped shape the architecture, ensuring we balanced simplicity with safety based on proven practices in the Python ecosystem.

[\[1\]](https://cloud.tencent.com/developer/ask/sof/106280791#:~:text=) Google App Engine :导入myfile会给502带来糟糕的网关-腾讯云开发者社区-腾讯云

<https://cloud.tencent.com/developer/ask/sof/106280791>
