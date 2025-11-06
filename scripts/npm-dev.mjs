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

const backendDir = ".";
const hasBackend = existsSync(join("apps", "api", "app")) && existsSync("pyproject.toml");
const hasFrontend =
  existsSync(join("apps", "web")) && existsSync(join("apps", "web", "package.json"));

const makeUvicornCommand = (port, extraArgs = []) => {
  const venvUvicorn =
    process.platform === "win32"
      ? join(backendDir, ".venv", "Scripts", "uvicorn.exe")
      : join(backendDir, ".venv", "bin", "uvicorn");
  const args = [
    "apps.api.app.main:create_app",
    "--factory",
    "--host",
    "0.0.0.0",
    "--port",
    `${port}`,
    ...extraArgs,
  ];

  if (existsSync(venvUvicorn)) {
    const quoted = venvUvicorn.includes(" ") ? `"${venvUvicorn}"` : venvUvicorn;
    return `${quoted} ${args.join(" ")}`;
  }

  return `uvicorn ${args.join(" ")}`;
};

const validModes = new Set(["backend", "frontend"]);
const [mode, ...rest] = process.argv.slice(2).filter(Boolean);

if (rest.length > 0) {
  console.error(`Unexpected arguments: ${rest.join(", ")}`);
  process.exit(1);
}

if (mode && !validModes.has(mode)) {
  console.error(`Unknown mode "${mode}". Use "backend" or "frontend".`);
  process.exit(1);
}

if (mode === "backend" && !hasBackend) {
  console.error("Backend not found. Ensure apps/api/app/ and pyproject.toml exist before running backend mode.");
  process.exit(1);
}

if (mode === "frontend" && !hasFrontend) {
  console.error("Frontend not found. Create apps/web/ before running frontend mode.");
  process.exit(1);
}

const runBackend = hasBackend && (!mode || mode === "backend");
const runFrontend = hasFrontend && (!mode || mode === "frontend");
const backendPort =
  process.env.DEV_BACKEND_PORT ??
  (runBackend && runFrontend ? "8001" : "8000");
const frontendPort = process.env.DEV_FRONTEND_PORT ?? "8000";

process.env.DEV_BACKEND_PORT = backendPort;
process.env.DEV_FRONTEND_PORT = frontendPort;

const tasks = [];

if (runBackend) {
  tasks.push({
    name: "backend",
    command: makeUvicornCommand(backendPort, ["--reload"]),
  });
}

if (runFrontend) {
  tasks.push({
    name: "frontend",
    command: `npm --prefix apps/web run dev -- --host 0.0.0.0 --port ${frontendPort}`,
  });
}

if (tasks.length === 0) {
  console.log("Nothing to run yet. Add apps/api/app/ and/or apps/web/ first.");
  process.exit(0);
}

await run("npx", [
  "concurrently",
  "-k",
  "-c",
  "auto",
  "-n",
  tasks.map(({ name }) => name).join(","),
  ...tasks.map(({ command }) => command),
]);
