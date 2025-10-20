import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const run = (command, args = [], options = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: "inherit",
      shell: false,
      ...options,
    });
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(" ")} exited with code ${code}`));
    });
  });

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

const hasBackend = existsSync("backend") && existsSync(join("backend", "app"));
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const collectFrontendRoutes = async () => {
  if (!hasFrontend) {
    return { status: "skipped", reason: "frontend missing" };
  }

  const nodeModulesDir = join("frontend", "node_modules");
  if (!existsSync(nodeModulesDir)) {
    return {
      status: "skipped",
      reason: "frontend dependencies not installed",
    };
  }

  const binary = process.platform === "win32" ? "react-router.cmd" : "react-router";
  const localBin = join(nodeModulesDir, ".bin", binary);
  const localBinAbsolute = join(process.cwd(), localBin);

  try {
    const { stdout } = existsSync(localBin)
      ? await runCapture(localBinAbsolute, ["routes", "--json"], {
          cwd: "frontend",
          shell: process.platform === "win32",
        })
      : await runCapture("npx", ["react-router", "routes", "--json"], {
          cwd: "frontend",
          shell: process.platform === "win32",
        });
    const parsed = JSON.parse(stdout);
    const routes = Array.isArray(parsed?.routes) ? parsed.routes : [];
    return { status: "ok", routes, raw: parsed };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { status: "failed", error: message };
  }
};

const steps = [];

const record = (name) => {
  const entry = { name, status: "pending" };
  steps.push(entry);
  return entry;
};

const formatStepLabel = (name) => name.replace(/[-_]/g, " ").toUpperCase();

const logStepStart = (name) => {
  console.log(`\n=== ${formatStepLabel(name)} :: START ===`);
};

const logStepSuccess = (name) => {
  console.log(`=== ${formatStepLabel(name)} :: OK ===`);
};

const logStepFailure = (name, error) => {
  console.error(`=== ${formatStepLabel(name)} :: FAILED ===`);

  if (error) {
    console.error(error instanceof Error ? error.message : String(error));
  }
};

const runStep = async (name, task) => {
  const entry = record(name);
  logStepStart(name);
  try {
    await task();
    entry.status = "ok";
    logStepSuccess(name);
  } catch (error) {
    entry.status = "failed";
    entry.error = error instanceof Error ? error.message : String(error);
    logStepFailure(name, error);
    throw error;
  }
};

await runStep("setup", () => run("npm", ["run", "setup"]));
await runStep("openapi-typescript", () => run("npm", ["run", "openapi-typescript"]));
await runStep("lint", () => run("npm", ["run", "lint"]));
await runStep("test", () => run("npm", ["run", "test"]));
await runStep("build", () => run("npm", ["run", "build"]));

const routesResult = await collectFrontendRoutes();
const routesStep = {
  name: "routes",
  status: routesResult.status,
  ...(routesResult.reason ? { reason: routesResult.reason } : {}),
  ...(routesResult.error ? { error: routesResult.error } : {}),
  ...(routesResult.status === "ok"
    ? { count: routesResult.routes.length }
    : {}),
};
steps.push(routesStep);

const okSteps = steps.every(
  (step) => step.status === "ok" || step.status === "skipped",
);

console.log("\n=== CI SUMMARY ===");
for (const step of steps) {
  const statusText = step.status.toUpperCase();
  if (step.status === "failed") {
    console.log(`- ${step.name}: ${statusText} (${step.error ?? "see logs"})`);
  } else if (step.status === "skipped") {
    console.log(`- ${step.name}: ${statusText}${step.reason ? ` (${step.reason})` : ""}`);
  } else {
    console.log(`- ${step.name}: ${statusText}`);
  }
}

const summary = {
  ok: okSteps && routesResult.status !== "failed",
  context: {
    backendPresent: hasBackend,
    frontendPresent: hasFrontend,
  },
  steps,
};

if (routesResult.status === "ok") {
  summary.routes = routesResult.routes;
}

console.log(JSON.stringify(summary, null, 2));
