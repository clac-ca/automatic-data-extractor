import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const runCapture = (command, args = [], options = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: ["ignore", "pipe", "pipe"],
      shell: false,
      ...options,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(stderr || `${command} ${args.join(" ")} exited with code ${code}`));
    });
  });

const hasFrontend =
  existsSync(join("apps", "web")) && existsSync(join("apps", "web", "package.json"));

const rawArgs = process.argv.slice(2).filter((arg) => arg !== "--");
const args = new Set(rawArgs);
const mode = args.has("--tree") ? "tree" : "json";
const compactOutput = mode === "json" && args.has("--compact");
const formatJson = (payload) =>
  compactOutput ? JSON.stringify(payload) : JSON.stringify(payload, null, 2);

const normalizeSegments = (segments) =>
  segments.filter((segment) => segment !== "");

const accumulateSegments = (parentSegments, route) => {
  if (route.index) {
    return parentSegments;
  }
  const pathSegment = route.path ?? "";
  if (pathSegment === "") {
    return parentSegments;
  }
  return [...parentSegments, pathSegment];
};

const formatFullPath = (segments) => {
  const normalized = normalizeSegments(segments);
  if (normalized.length === 0) {
    return "/";
  }
  return `/${normalized.join("/")}`.replace(/\/+/g, "/");
};

const renderRoutesTree = (routes, parentSegments = [], prefix = "", lines = [], isRoot = false) => {
  if (!Array.isArray(routes) || routes.length === 0) {
    return lines;
  }

  routes.forEach((route, index) => {
    const segments = accumulateSegments(parentSegments, route);
    const isLast = index === routes.length - 1;
    const connector = isRoot ? "" : isLast ? "└─ " : "├─ ";

    const fullPath = formatFullPath(segments);
    const isCatchAll = route.path === "*";
    const labelPath = route.index ? `${fullPath} [index]` : fullPath;
    const extras = [
      isCatchAll ? "catch-all" : null,
      route.path === undefined && !route.index ? "pathless" : null,
    ]
      .filter(Boolean)
      .map((tag) => `[${tag}]`)
      .join(" ");
    const fileLabel = route.file ?? "<unknown>";

    const descriptor = extras ? `${labelPath} ${extras}` : labelPath;
    lines.push(`${prefix}${connector}${descriptor} → ${fileLabel}`);

    const childPrefix = isRoot ? "" : `${prefix}${isLast ? "   " : "│  "}`;
    renderRoutesTree(route.children, segments, childPrefix, lines, false);
  });

  return lines;
};

const collectFrontendRoutes = async () => {
  if (!hasFrontend) {
    return { status: "skipped", reason: "frontend missing" };
  }

  return { status: "skipped", reason: "routerless frontend" };
};

const result = await collectFrontendRoutes();

if (result.status === "ok") {
  if (mode === "tree") {
    const lines = renderRoutesTree(result.routes, [], "", [], true);
    console.log(lines.length > 0 ? lines.join("\n") : "(no routes discovered)");
  } else {
    console.log(formatJson({ ok: true, routes: result.routes }));
  }
  process.exit(0);
}

const payload = {
  ok: false,
  status: result.status,
  ...(result.reason ? { reason: result.reason } : {}),
  ...(result.error ? { error: result.error } : {}),
};

console.log(formatJson(payload));

if (result.status === "failed") {
  process.exit(1);
}
