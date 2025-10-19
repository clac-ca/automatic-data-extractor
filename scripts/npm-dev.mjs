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

const hasBackend = existsSync("backend") && existsSync(join("backend", "app"));
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const makeUvicornCommand = (extraArgs = []) => {
  const backendDir = "backend";
  const venvUvicorn =
    process.platform === "win32"
      ? join(backendDir, ".venv", "Scripts", "uvicorn.exe")
      : join(backendDir, ".venv", "bin", "uvicorn");
  const args = [
    "app.main:app",
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

const commands = [];

if (hasBackend) {
  commands.push(makeUvicornCommand(["--reload"]));
}

if (hasFrontend) {
  commands.push("npm --prefix frontend run dev");
}

if (commands.length === 0) {
  console.log("Nothing to run yet. Add backend/ and/or frontend/ first.");
  process.exit(0);
}

await run("npx", [
  "concurrently",
  "-k",
  "-n",
  "api,web",
  "-c",
  "auto",
  ...commands,
]);
