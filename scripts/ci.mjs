import {
  hasBackend,
  hasFrontend,
  run,
  collectFrontendRoutes,
} from "./_helpers.mjs";

const steps = [];

const record = (name) => {
  const entry = { name, status: "pending" };
  steps.push(entry);
  return entry;
};

const runStep = async (name, task) => {
  const entry = record(name);
  try {
    await task();
    entry.status = "ok";
  } catch (error) {
    entry.status = "failed";
    entry.error = error instanceof Error ? error.message : String(error);
    throw error;
  }
};

await runStep("setup", () => run("npm", ["run", "setup"]));
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

const summary = {
  ok: okSteps && routesResult.status !== "failed",
  context: {
    backendPresent: hasBackend(),
    frontendPresent: hasFrontend(),
  },
  steps,
};

if (routesResult.status === "ok") {
  summary.routes = routesResult.routes;
}

console.log(JSON.stringify(summary, null, 2));
