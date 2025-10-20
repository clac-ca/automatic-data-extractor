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
const hasBackend = existsSync(join("backend", "app")) && existsSync("pyproject.toml");
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const makeUvicornCommand = (extraArgs = []) => {
  const venvUvicorn =
    process.platform === "win32"
      ? join(backendDir, ".venv", "Scripts", "uvicorn.exe")
      : join(backendDir, ".venv", "bin", "uvicorn");
  const args = [
    "backend.app.app:create_app",
    "--factory",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
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
  console.error("Backend not found. Ensure backend/app/ and pyproject.toml exist before running backend mode.");
  process.exit(1);
}

if (mode === "frontend" && !hasFrontend) {
  console.error("Frontend not found. Create frontend/ before running frontend mode.");
  process.exit(1);
}

const tasks = [];

if (hasBackend && (!mode || mode === "backend")) {
  tasks.push({
    name: "backend",
    command: makeUvicornCommand(["--reload"]),
  });
}

if (hasFrontend && (!mode || mode === "frontend")) {
  tasks.push({
    name: "frontend",
    command: "npm --prefix frontend run dev",
  });
}

if (tasks.length === 0) {
  console.log("Nothing to run yet. Add backend/app/ and/or frontend/ first.");
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
