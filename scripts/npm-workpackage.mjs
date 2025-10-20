import { promises as fs } from "node:fs";
import { existsSync, watch, createReadStream } from "node:fs";
import readline from "node:readline";
import { join, dirname, relative } from "node:path";

const ROOT = process.cwd();
const WP_DIR = join(ROOT, ".workpackage");
const PACKAGES_DIR = join(WP_DIR, "packages");
const INDEX_FILE = join(PACKAGES_DIR, "index.json");
const LOCK_DIR = join(WP_DIR, ".lock");
const LOCK_RETRY_MS = 50;
const LOCK_TIMEOUT_MS = 10000;
const LOCK_CLEANUP_ATTEMPTS = 3;
const STATUSES = new Set([
  "draft",
  "active",
  "blocked",
  "done",
  "dropped",
  "cancelled",
]);
const INACTIVE_STATUSES = new Set(["done", "dropped", "cancelled"]);

const nowIso = () => new Date().toISOString();
const pad4 = (value) => String(value).padStart(4, "0");
const toSlug = (value) =>
  value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
const currentUser = () =>
  process.env.GIT_AUTHOR_NAME ||
  process.env.GIT_COMMITTER_NAME ||
  process.env.USER ||
  process.env.USERNAME ||
  "unknown";

const readJson = async (path, fallback = undefined) => {
  try {
    const raw = await fs.readFile(path, "utf8");
    return JSON.parse(raw);
  } catch (error) {
    if (fallback !== undefined) return fallback;
    throw error;
  }
};

const writeJson = async (path, payload) => {
  const targetDir = dirname(path);
  await fs.mkdir(targetDir, { recursive: true });
  const tmpPath = join(
    targetDir,
    `${relative(targetDir, path)}.${process.pid}.${Date.now()}.tmp`,
  );
  const json = JSON.stringify(payload, null, 2) + "\n";
  await fs.writeFile(tmpPath, json, "utf8");
  await fs.rm(path, { force: true });
  await fs.rename(tmpPath, path);
};

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const acquireLock = async (timeoutMs = LOCK_TIMEOUT_MS) => {
  const start = Date.now();
  let cleanupAttempts = 0;
  while (true) {
    try {
      await fs.mkdir(LOCK_DIR);
      return;
    } catch (error) {
      if (error?.code === "EEXIST") {
        if (Date.now() - start > timeoutMs) {
          throw new Error("Timed out acquiring workpackage lock");
        }
        if (cleanupAttempts < LOCK_CLEANUP_ATTEMPTS) {
          cleanupAttempts += 1;
          try {
            const stats = await fs.stat(LOCK_DIR);
            if (Date.now() - stats.mtimeMs > timeoutMs) {
              await fs.rm(LOCK_DIR, { recursive: true, force: true });
            }
          } catch {
            // ignore stat/remove errors
          }
        }
        await delay(LOCK_RETRY_MS);
        continue;
      }
      throw error;
    }
  }
};

const releaseLock = async () => {
  await fs.rm(LOCK_DIR, { recursive: true, force: true });
};

const withLock = async (callback) => {
  await acquireLock();
  try {
    return await callback();
  } finally {
    await releaseLock();
  }
};

const ensureStructure = async () => {
  await fs.mkdir(PACKAGES_DIR, { recursive: true });
  if (!existsSync(INDEX_FILE)) {
    await writeJson(INDEX_FILE, { version: 1, lastNumber: 0, packages: [] });
  }
};

const loadIndex = async () => {
  await ensureStructure();
  const index = await readJson(INDEX_FILE, { version: 1, lastNumber: 0, packages: [] });
  if (!Array.isArray(index.packages)) index.packages = [];
  if (typeof index.lastNumber !== "number") index.lastNumber = 0;
  return index;
};

const saveIndex = async (index) => writeJson(INDEX_FILE, index);

const reindex = async () => {
  await ensureStructure();
  const entries = await fs.readdir(PACKAGES_DIR, { withFileTypes: true });
  const packages = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dir = join(PACKAGES_DIR, entry.name);
    const wpPath = join(dir, "workpackage.json");
    if (!existsSync(wpPath)) continue;
    try {
      const wp = await readJson(wpPath);
      const validation = validateWorkpackageData(wp, `workpackage at ${wpPath}`);
      if (!validation.valid) {
        continue;
      }
      packages.push({
        number: wp.number,
        slug: wp.slug,
        title: wp.title,
        status: wp.status,
        summary: wp.summary,
        createdAt: wp.createdAt,
        updatedAt: wp.updatedAt,
        path: dir,
      });
    } catch {
      continue;
    }
  }
  packages.sort((a, b) => (a.number || 0) - (b.number || 0));
  const lastNumber = packages.reduce(
    (max, pkg) => Math.max(max, Number(pkg.number) || 0),
    0,
  );
  const index = { version: 1, lastNumber, packages };
  await saveIndex(index);
  return index;
};

const promptConfirm = async (question) => {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  const answer = await new Promise((resolve) => rl.question(`${question} `, resolve));
  rl.close();
  return answer.trim().toLowerCase();
};

const resolveRef = async (ref, { reindexOnMiss = true } = {}) => {
  let index = await loadIndex();
  const target = lookupIndex(index, ref);
  if (target || !reindexOnMiss) return target;
  index = await reindex();
  return lookupIndex(index, ref);
};

const lookupIndex = (index, ref) => {
  if (!ref) return null;
  const isNumber = /^\d+$/.test(ref);
  const key = isNumber ? "number" : "slug";
  const value = isNumber ? Number(ref) : ref;
  const entry = index.packages.find((item) => item[key] === value);
  if (!entry) return null;
  const dir = entry.path || join(PACKAGES_DIR, `${pad4(entry.number)}-${entry.slug}`);
  return {
    dir,
    wpPath: join(dir, "workpackage.json"),
    logPath: join(dir, "log.ndjson"),
    notesPath: join(dir, "notes.md"),
    entry,
  };
};

const appendLog = async (dir, event) => {
  const line = JSON.stringify({ at: nowIso(), user: currentUser(), ...event }) + "\n";
  await fs.appendFile(join(dir, "log.ndjson"), line, "utf8");
};

const updateIndexEntry = async (number, patch) => {
  const index = await loadIndex();
  const idx = index.packages.findIndex((item) => item.number === number);
  if (idx >= 0) {
    index.packages[idx] = { ...index.packages[idx], ...patch };
  }
  await saveIndex(index);
};

const updateNotesStatus = async (path, status) => {
  if (!existsSync(path)) return;
  const text = await fs.readFile(path, "utf8");
  const next = text.replace(/Status:\s.*\n/, `Status: ${status}\n`);
  await fs.writeFile(path, next, "utf8");
};

const appendNoteToFile = async (path, text) => {
  await fs.appendFile(path, `- ${nowIso()} • ${currentUser()}: ${text}\n`, "utf8");
};

const parseTags = (raw) =>
  (raw || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

const getArg = (argv, flag) => {
  const index = argv.indexOf(flag);
  if (index === -1) return undefined;
  const next = argv[index + 1];
  if (!next || next.startsWith("--")) return "";
  return next;
};

const parseStatus = (value) => {
  if (!value) return undefined;
  const trimmed = value.trim().toLowerCase();
  return STATUSES.has(trimmed) ? trimmed : undefined;
};

const isIsoDate = (value) => {
  if (typeof value !== "string") return false;
  const date = Date.parse(value);
  return Number.isFinite(date);
};

const validateString = (value, { allowEmpty = true } = {}) =>
  typeof value === "string" && (allowEmpty || value.trim().length > 0);

const isStringArray = (value) =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const isObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const validateWorkpackageData = (data, context = "workpackage") => {
  const errors = [];
  if (!isObject(data)) {
    errors.push(`${context}: expected object`);
    return { valid: false, errors };
  }
  if (!validateString(data.version, { allowEmpty: false })) {
    errors.push(`${context}.version must be a non-empty string`);
  }
  if (!Number.isFinite(data.number)) {
    errors.push(`${context}.number must be a number`);
  }
  if (!validateString(data.slug, { allowEmpty: false })) {
    errors.push(`${context}.slug must be a non-empty string`);
  }
  if (!validateString(data.title, { allowEmpty: false })) {
    errors.push(`${context}.title must be a non-empty string`);
  }
  if (!validateString(data.summary)) {
    errors.push(`${context}.summary must be a string`);
  }
  if (!validateString(data.status, { allowEmpty: false }) || !STATUSES.has(data.status)) {
    errors.push(`${context}.status must be one of ${Array.from(STATUSES).join(", ")}`);
  }
  if (!validateString(data.owner, { allowEmpty: false })) {
    errors.push(`${context}.owner must be a non-empty string`);
  }
  if (!isIsoDate(data.createdAt)) {
    errors.push(`${context}.createdAt must be an ISO timestamp`);
  }
  if (!isIsoDate(data.updatedAt)) {
    errors.push(`${context}.updatedAt must be an ISO timestamp`);
  }
  if (data.tags !== undefined && !isStringArray(data.tags)) {
    errors.push(`${context}.tags must be an array of strings`);
  }
  if (data.links !== undefined && !Array.isArray(data.links)) {
    errors.push(`${context}.links must be an array`);
  }
  if (data.context !== undefined && !isObject(data.context)) {
    errors.push(`${context}.context must be an object`);
  }
  return { valid: errors.length === 0, errors };
};

const validationFail = (errors, context) =>
  fail("ERR_VALIDATION_FAILED", `Invalid ${context}`, { errors });

const fail = (code, message, extra = {}) => ({
  ok: false,
  error: message,
  code,
  ...extra,
});

const stripOk = (payload) => {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return payload;
  const { ok, ...rest } = payload;
  return rest;
};

const toAgentEnvelope = (payload, { command, startedAt, durationMs, exitCode }) => {
  const timestamp = nowIso();
  if (payload?.ok === false) {
    const { error, code, ok: _ok, ...details } = payload || {};
    const errorDetails = Object.keys(details).length ? details : undefined;
    return {
      ok: false,
      status: "error",
      command,
      timestamp,
      startedAt,
      durationMs,
      exitCode,
      error: {
        message: error || "unknown error",
        ...(code ? { code } : {}),
        ...(errorDetails ? { details: errorDetails } : {}),
      },
    };
  }
  return {
    ok: true,
    status: "ok",
    command,
    timestamp,
    startedAt,
    durationMs,
    exitCode,
    data: stripOk(payload),
  };
};

const parseGlobalOptions = (argv) => {
  const options = { mode: "agent", exitOnError: true };
  let index = 0;
  while (index < argv.length) {
    const arg = argv[index];
    if (arg === "--") {
      index += 1;
      break;
    }
    if (arg === "--plain" || arg === "--human") {
      options.mode = "plain";
      index += 1;
      continue;
    }
    if (arg === "--agent" || arg === "-a") {
      options.mode = "agent";
      index += 1;
      continue;
    }
    if (arg === "--no-exit") {
      options.exitOnError = false;
      index += 1;
      continue;
    }
    if (!arg.startsWith("-") || arg === "-") {
      break;
    }
    break;
  }
  return { options, args: argv.slice(index) };
};

const normalizeCommand = (value) => {
  if (!value) return undefined;
  if (value === "--help" || value === "-h") return "help";
  return value;
};

const describePaths = (entries) =>
  Object.fromEntries(
    Object.entries(entries).map(([key, absolutePath]) => [
      key,
      {
        absolute: absolutePath,
        relative: relative(ROOT, absolutePath),
      },
    ]),
  );

const applyInlineGlobalOptions = (argv, cliOptions) => {
  if (!Array.isArray(argv) || argv.length === 0) {
    return { args: argv ?? [] };
  }
  const nextArgs = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--") {
      nextArgs.push(arg, ...argv.slice(index + 1));
      break;
    }
    if (arg === "--plain" || arg === "--human") {
      cliOptions.mode = "plain";
      continue;
    }
    if (arg === "--agent" || arg === "-a") {
      cliOptions.mode = "agent";
      continue;
    }
    if (arg === "--no-exit") {
      cliOptions.exitOnError = false;
      continue;
    }
    nextArgs.push(arg);
  }
  return { args: nextArgs };
};

// Commands
const cmdInit = async () => {
  await ensureStructure();
  const index = await loadIndex();
  return { ok: true, action: "init", lastNumber: index.lastNumber, generatedAt: nowIso() };
};

const parseStatusesArg = (raw) =>
  (raw || "")
    .split(",")
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean);

const describeSummary = (value) => {
  const text = (value || "").replace(/\s+/g, " ").trim();
  if (!text) return "No summary provided yet.";
  const limit = 160;
  return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
};

const cmdList = async (argv = []) => {
  const index = await loadIndex();
  const statusArg = getArg(argv, "--status");
  const includeActive = argv.includes("--active");

  if (statusArg === "") {
    return fail("ERR_LIST_STATUS_REQUIRED", "--status requires at least one status value");
  }

  const statusFilters = new Set();
  if (includeActive) statusFilters.add("active");
  if (statusArg !== undefined) {
    const parsed = parseStatusesArg(statusArg);
    const invalid = parsed.filter((status) => !STATUSES.has(status));
    if (invalid.length > 0) {
      return fail("ERR_LIST_STATUS_INVALID", "One or more statuses are invalid", {
        provided: Array.from(new Set([...parsed])),
        invalid,
        allowed: Array.from(STATUSES),
      });
    }
    parsed.forEach((status) => statusFilters.add(status));
  }

  const filterStatuses = statusFilters.size > 0 ? Array.from(statusFilters) : null;
  const packagesAll = await Promise.all(
    index.packages.map(async (entry) => {
      const dir = entry.path || join(PACKAGES_DIR, `${pad4(entry.number)}-${entry.slug}`);
      let summaryText = entry.summary;
      if (summaryText === undefined) {
        try {
          const workpackage = await readJson(join(dir, "workpackage.json"));
          summaryText = workpackage.summary || "";
        } catch {
          summaryText = "";
        }
      }
      return {
        number: entry.number,
        slug: entry.slug,
        title: entry.title,
        status: entry.status,
        updatedAt: entry.updatedAt,
        summary: summaryText,
        description: describeSummary(summaryText),
      };
    }),
  );

  const summary = packagesAll.reduce(
    (acc, pkg) => {
      const statusKey = pkg.status || "unknown";
      acc.byStatus[statusKey] = (acc.byStatus[statusKey] || 0) + 1;
      return acc;
    },
    { total: index.packages.length, byStatus: {} },
  );

  const packages = packagesAll.filter((item) => {
    if (filterStatuses) return filterStatuses.includes(item.status);
    return !INACTIVE_STATUSES.has(item.status);
  });

  return {
    ok: true,
    generatedAt: nowIso(),
    total: index.packages.length,
    count: packages.length,
    summary,
    ...(filterStatuses
      ? {
          filters: {
            status: filterStatuses,
          },
        }
      : {}),
    packages,
  };
};

const cmdCreate = async (argv) =>
  withLock(async () => {
    const title = getArg(argv, "--title");
    if (!title) return fail("ERR_CREATE_TITLE_REQUIRED", "--title is required");

    const summary = getArg(argv, "--summary") || "";
    const owner = getArg(argv, "--owner") || currentUser();
    const tags = parseTags(getArg(argv, "--tags"));
    const desiredStatus = parseStatus(getArg(argv, "--status"));
    const status = desiredStatus || "draft";

    const index = await loadIndex();
    const number = index.lastNumber + 1;
    const slugBase = toSlug(title);
    const slug = slugBase || `wp-${pad4(number)}`;
    const folder = `${pad4(number)}-${slug}`;
    const dir = join(PACKAGES_DIR, folder);

    if (existsSync(dir)) {
      return fail("ERR_CREATE_EXISTS", `directory already exists: ${folder}`, { folder });
    }

    await fs.mkdir(join(dir, "attachments"), { recursive: true });

    const timestamp = nowIso();
    const workpackage = {
      version: "1",
      number,
      slug,
      title,
      summary,
      status,
      createdAt: timestamp,
      updatedAt: timestamp,
      owner,
      tags,
      links: [],
      context: {},
    };

    const validation = validateWorkpackageData(workpackage, "workpackage");
    if (!validation.valid) {
      return validationFail(validation.errors, "workpackage");
    }

    const workpackagePath = join(dir, "workpackage.json");
    const notesPath = join(dir, "notes.md");
    const logPath = join(dir, "log.ndjson");

    await writeJson(workpackagePath, workpackage);

    const notesHeader = `# ${title}\n\nOwner: ${owner}\nStatus: ${status}\nCreated: ${timestamp}\n\n---\n`;
    await fs.writeFile(notesPath, notesHeader, "utf8");
    await fs.writeFile(logPath, "", "utf8");
    await appendLog(dir, { type: "create", data: { title, status, tags } });

    index.lastNumber = number;
    index.packages.push({
      number,
      slug,
      title,
      status,
      summary,
      createdAt: timestamp,
      updatedAt: timestamp,
      path: dir,
    });
    await saveIndex(index);

    return {
      ok: true,
      number,
      slug,
      status,
      paths: describePaths({
        dir,
        workpackage: workpackagePath,
        notes: notesPath,
        log: logPath,
      }),
    };
  });

const cmdShow = async (ref) => {
  const resolved = await resolveRef(ref);
  if (!resolved) return fail("ERR_LOOKUP_NOT_FOUND", `workpackage not found: ${ref}`, { ref });
  const workpackage = await readJson(resolved.wpPath);
  const validation = validateWorkpackageData(workpackage, "workpackage");
  if (!validation.valid) {
    return validationFail(validation.errors, "workpackage");
  }
  return {
    ok: true,
    workpackage,
    paths: describePaths({
      dir: resolved.dir,
      workpackage: resolved.wpPath,
      notes: resolved.notesPath,
      log: resolved.logPath,
    }),
  };
};

const cmdStatus = async (ref, argv) =>
  withLock(async () => {
    const target = await resolveRef(ref);
    if (!target) return fail("ERR_LOOKUP_NOT_FOUND", `workpackage not found: ${ref}`, { ref });
    const status = parseStatus(getArg(argv, "--to"));
    if (!status) {
      return fail(
        "ERR_STATUS_INVALID",
        "--to must be one of draft|active|blocked|done|dropped",
        { provided: getArg(argv, "--to") },
      );
    }

    const workpackage = await readJson(target.wpPath);
    const validationBefore = validateWorkpackageData(workpackage, "workpackage");
    if (!validationBefore.valid) {
      return validationFail(validationBefore.errors, "workpackage");
    }

    workpackage.status = status;
    workpackage.updatedAt = nowIso();

    const validationAfter = validateWorkpackageData(workpackage, "workpackage");
    if (!validationAfter.valid) {
      return validationFail(validationAfter.errors, "workpackage");
    }

    await writeJson(target.wpPath, workpackage);
    await updateIndexEntry(workpackage.number, {
      status,
      updatedAt: workpackage.updatedAt,
      slug: workpackage.slug,
      title: workpackage.title,
      summary: workpackage.summary,
    });
    await updateNotesStatus(target.notesPath, status);
    await appendLog(target.dir, { type: "status", data: { status } });

    return {
      ok: true,
      status,
      workpackage,
      paths: describePaths({
        dir: target.dir,
        workpackage: target.wpPath,
        notes: target.notesPath,
        log: target.logPath,
      }),
    };
  });

const cmdDelete = async (ref, argv) =>
  withLock(async () => {
    const confirm = argv.includes("--yes") || argv.includes("--force");
    if (!confirm) {
      return fail("ERR_DELETE_CONFIRM_REQUIRED", "Deletion requires --yes (or --force) to proceed.", {
        ref,
      });
    }

    const target = await resolveRef(ref);
    if (!target) return fail("ERR_LOOKUP_NOT_FOUND", `workpackage not found: ${ref}`, { ref });

    let snapshot = null;
    try {
      snapshot = await readJson(target.wpPath);
    } catch {
      // ignore snapshot failures; proceed with best-effort delete
    }

    try {
      await fs.rm(target.dir, { recursive: true, force: true });
    } catch (error) {
      return fail(
        "ERR_DELETE_FAILED",
        `Failed removing workpackage directory for ${ref}`,
        {
          ref,
          error: error instanceof Error ? error.message : String(error),
        },
      );
    }

    const index = await loadIndex();
    const before = index.packages.length;
    index.packages = index.packages.filter(
      (entry) => entry.number !== target.entry.number,
    );
    if (index.packages.length === before) {
      return fail(
        "ERR_DELETE_MISMATCH",
        "Workpackage directory removed but index update failed; consider reindexing.",
        { ref },
      );
    }
    index.lastNumber = index.packages.reduce(
      (max, entry) => Math.max(max, Number(entry.number) || 0),
      0,
    );
    await saveIndex(index);

    return {
      ok: true,
      deleted: {
        number: target.entry.number,
        slug: target.entry.slug,
        title: target.entry.title,
      },
      workpackage: snapshot ?? undefined,
      paths: describePaths({
        dir: target.dir,
        workpackage: target.wpPath,
        notes: target.notesPath,
        log: target.logPath,
      }),
    };
  });

const cmdNote = async (ref, argv) =>
  withLock(async () => {
    const target = await resolveRef(ref);
    if (!target) return fail("ERR_LOOKUP_NOT_FOUND", `workpackage not found: ${ref}`, { ref });
    const text = getArg(argv, "--text") || getArg(argv, "-m");
    if (!text) return fail("ERR_NOTE_TEXT_REQUIRED", "--text is required");

    await appendLog(target.dir, { type: "note", data: { text } });
    await appendNoteToFile(target.notesPath, text);
    return {
      ok: true,
      note: { text },
      paths: describePaths({
        dir: target.dir,
        notes: target.notesPath,
        log: target.logPath,
      }),
    };
  });

const cmdReindex = async () =>
  withLock(async () => {
    const index = await reindex();
    return {
      ok: true,
      generatedAt: nowIso(),
      count: index.packages.length,
      lastNumber: index.lastNumber,
    };
  });

const cmdClear = async () =>
  withLock(async () => {
    await ensureStructure();
    const index = await loadIndex();
    if (index.packages.length === 0) {
      return {
        ok: true,
        cleared: 0,
        message: "No workpackages to clear.",
      };
    }

    const answer = await promptConfirm(
      `⚠️  This will permanently delete ${index.packages.length} workpackages. Type "yes" to confirm:`,
    );
    if (answer !== "yes") {
      return {
        ok: false,
        code: "ERR_CLEAR_ABORTED",
        error: "Clear operation aborted by user.",
      };
    }

    for (const entry of index.packages) {
      const dir = entry.path || join(PACKAGES_DIR, `${pad4(entry.number)}-${entry.slug}`);
      try {
        await fs.rm(dir, { recursive: true, force: true });
      } catch {
        // continue even if we fail removing a directory
      }
    }

    await writeJson(INDEX_FILE, { version: 1, lastNumber: 0, packages: [] });
    return {
      ok: true,
      cleared: index.packages.length,
    };
  });

const collectNoteMatches = (content, needle, limit = 3) => {
  const matches = [];
  const lines = content.split(/\r?\n/);
  for (const line of lines) {
    if (!line) continue;
    if (line.toLowerCase().includes(needle)) {
      matches.push(line.trim());
      if (matches.length >= limit) break;
    }
  }
  return matches;
};

const cmdFind = async (query) => {
  const term = (query || "").trim();
  if (!term) return fail("ERR_FIND_QUERY_REQUIRED", "find requires a search term");
  const needle = term.toLowerCase();

  const index = await loadIndex();
  const results = [];

  for (const entry of index.packages) {
    const dir = entry.path || join(PACKAGES_DIR, `${pad4(entry.number)}-${entry.slug}`);
    const notesPath = join(dir, "notes.md");
    const matches = [];
    const title = entry.title || "";
    const summary = entry.summary || "";
    if (title.toLowerCase().includes(needle)) {
      matches.push({ field: "title", snippet: title });
    }
    if (summary.toLowerCase().includes(needle)) {
      matches.push({ field: "summary", snippet: describeSummary(summary) });
    }
    try {
      const notes = await fs.readFile(notesPath, "utf8");
      const noteMatches = collectNoteMatches(notes, needle);
      for (const snippet of noteMatches) {
        matches.push({ field: "notes", snippet });
      }
    } catch {
      // ignore missing notes
    }
    if (matches.length > 0) {
      results.push({
        number: entry.number,
        slug: entry.slug,
        title,
        status: entry.status,
        summary: describeSummary(summary),
        updatedAt: entry.updatedAt,
        matches,
      });
    }
  }

  return {
    ok: true,
    generatedAt: nowIso(),
    query: term,
    count: results.length,
    results,
  };
};

const cmdBoard = async () => {
  const index = await loadIndex();
  const columns = [];
  const statuses = Array.from(STATUSES);
  for (const status of statuses) {
    const items = index.packages
      .filter((pkg) => pkg.status === status)
      .sort(
        (a, b) =>
          new Date(b.updatedAt || 0).getTime() - new Date(a.updatedAt || 0).getTime(),
      );
    const topItems = items.slice(0, 5).map((pkg) => ({
      number: pkg.number,
      slug: pkg.slug,
      title: pkg.title,
      summary: describeSummary(pkg.summary || ""),
      updatedAt: pkg.updatedAt,
    }));
    columns.push({
      status,
      count: items.length,
      items: topItems,
    });
  }

  return {
    ok: true,
    generatedAt: nowIso(),
    columns,
  };
};

const tailOutputLine = (line, mode) => {
  if (!line) return;
  if (mode === "agent") {
    let parsed;
    try {
      parsed = JSON.parse(line);
    } catch {
      parsed = null;
    }
    const payload = parsed
      ? { entry: parsed, raw: line }
      : { raw: line };
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  } else {
    process.stdout.write(`${line}\n`);
  }
};

const readFileSegment = (path, start, mode, state) =>
  new Promise((resolve) => {
    const stream = createReadStream(path, { encoding: "utf8", start });
    let buffer = "";
    stream.on("data", (chunk) => {
      buffer += chunk;
      let newlineIndex;
      while ((newlineIndex = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        tailOutputLine(line, mode);
      }
    });
    stream.on("end", () => {
      state.position = start + stream.bytesRead;
      if (buffer.length > 0) {
        tailOutputLine(buffer, mode);
        buffer = "";
      }
      resolve();
    });
    stream.on("error", () => resolve());
  });

const cmdTail = async (ref, { mode }) => {
  const target = await resolveRef(ref);
  if (!target) return fail("ERR_LOOKUP_NOT_FOUND", `workpackage not found: ${ref}`, { ref });

  const logPath = target.logPath;
  await fs.mkdir(dirname(logPath), { recursive: true });
  const exists = existsSync(logPath);
  if (!exists) {
    await fs.writeFile(logPath, "", "utf8");
  }

  const header = {
    ok: true,
    status: "stream",
    command: "tail",
    timestamp: nowIso(),
    data: describePaths({ log: logPath }),
  };
  process.stdout.write(`${JSON.stringify(header, null, 2)}\n`);

  const state = { position: 0 };
  await readFileSegment(logPath, 0, mode, state);

  let watcher;
  const attachWatcher = () => {
    watcher = watch(logPath, async (eventType) => {
      if (eventType === "rename") {
        watcher.close();
        state.position = 0;
        await delay(100);
        await readFileSegment(logPath, 0, mode, state);
        attachWatcher();
        return;
      }
      await readFileSegment(logPath, state.position, mode, state);
    });
  };

  attachWatcher();

  const cleanup = () => {
    if (watcher) watcher.close();
    process.exit(0);
  };

  process.on("SIGINT", cleanup);
  process.on("SIGTERM", cleanup);

  return null;
};

const help = () => ({
  ok: true,
  generatedAt: nowIso(),
  usage: "npm run workpackage <command> [options]",
  description: "Manage .workpackage/ records. Defaults optimized for AI agents (agent envelope + readable JSON).",
  commands: [
    "init",
    "list [--active] [--status <statuses>]",
    "create -- --title <title> [--summary <text>] [--tags t1,t2]",
    "show <number|slug>",
    "status <number|slug> -- --to <status>",
    "delete <number|slug> -- --yes",
    "note <number|slug> -- --text <message>",
    "reindex",
    "find <text>",
    "tail <number|slug>",
    "board",
    "clear",
  ],
  statuses: Array.from(STATUSES),
  globalFlags: [
    "--agent               # force agent envelope output (default)",
    "--plain / --human     # raw payload without agent envelope",
    "--no-exit             # keep exit code 0 even when ok:false",
  ],
});

// Entry
const rawArgv = process.argv.slice(2);
const { options: cliOptions, args: argv } = parseGlobalOptions(rawArgv);
const commandInput = argv[0];
const command = normalizeCommand(commandInput);
const { args: inlineArgs } = applyInlineGlobalOptions(
  command ? argv.slice(1) : argv,
  cliOptions,
);
const commandArgs = command ? inlineArgs : [];

const execution = { startedAt: new Date() };

const respond = (payload, { exitOnError, commandName } = {}) => {
  const finalCommand = commandName || command || "unknown";
  const durationMs = Math.max(0, Date.now() - execution.startedAt.getTime());
  const shouldExitOnError =
    exitOnError !== undefined ? exitOnError : cliOptions.exitOnError;
  const isError = payload?.ok === false;
  const exitCode = isError && shouldExitOnError ? 1 : 0;

  const body =
    cliOptions.mode === "agent"
      ? toAgentEnvelope(payload ?? {}, {
          command: finalCommand,
          startedAt: execution.startedAt.toISOString(),
          durationMs,
          exitCode,
        })
      : payload ?? {};

  if (cliOptions.mode === "agent") {
    body.exitCode = exitCode;
    body.durationMs = durationMs;
  }

  process.stdout.write(`${JSON.stringify(body, null, 2)}\n`);
  process.exit(exitCode);
};

(async () => {
  try {
    switch (command) {
      case undefined:
      case "help":
        respond(help(), { exitOnError: false, commandName: "help" });
        break;
      case "init":
        respond(await cmdInit(), { commandName: "init" });
        break;
      case "list":
        respond(await cmdList(commandArgs), { commandName: "list" });
        break;
      case "create":
        respond(await cmdCreate(commandArgs), { commandName: "create" });
        break;
      case "show":
        if (!commandArgs[0]) throw new Error("show requires a reference");
        respond(await cmdShow(commandArgs[0]), { commandName: "show" });
        break;
      case "status":
        if (!commandArgs[0]) throw new Error("status requires a reference");
        respond(await cmdStatus(commandArgs[0], commandArgs.slice(1)), {
          commandName: "status",
        });
        break;
      case "delete":
        if (!commandArgs[0]) throw new Error("delete requires a reference");
        respond(await cmdDelete(commandArgs[0], commandArgs.slice(1)), {
          commandName: "delete",
        });
        break;
      case "note":
        if (!commandArgs[0]) throw new Error("note requires a reference");
        respond(await cmdNote(commandArgs[0], commandArgs.slice(1)), {
          commandName: "note",
        });
        break;
      case "find":
        respond(await cmdFind(commandArgs.join(" ")), {
          commandName: "find",
        });
        break;
      case "board":
        respond(await cmdBoard(), { commandName: "board" });
        break;
      case "tail": {
        if (!commandArgs[0]) throw new Error("tail requires a reference");
        const response = await cmdTail(commandArgs[0], {
          mode: cliOptions.mode,
        });
        if (response) {
          respond(response, { commandName: "tail" });
        }
        return;
      }
      case "reindex":
        respond(await cmdReindex(), { commandName: "reindex" });
        break;
      case "clear":
        respond(await cmdClear(), { commandName: "clear" });
        break;
      default:
        respond(fail("ERR_UNKNOWN_COMMAND", `unknown command: ${command}`), {
          commandName: command || "unknown",
        });
        break;
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    respond(fail("ERR_UNEXPECTED", message), {
      commandName: command || "unknown",
    });
  }
})();
