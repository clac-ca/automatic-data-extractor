import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { stdin as input, stdout as output, env } from "node:process";

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

const lifecycle = env.npm_lifecycle_event ?? "";
const autoForce = lifecycle === "reset:force";
const isInteractive = Boolean(input.isTTY && output.isTTY);

if (!autoForce && !isInteractive) {
  console.log("⚠️ skipping reset; confirmation required. Use `npm run reset:force` to proceed non-interactively.");
  process.exit(0);
}

if (autoForce) {
  console.log("reset:force detected – running without confirmation.");
}

const pythonCandidates = process.platform === "win32"
  ? [
      join(process.cwd(), ".venv", "Scripts", "python.exe"),
      join(process.cwd(), ".venv", "Scripts", "python3.exe"),
      join(process.cwd(), ".venv", "Scripts", "python"),
      join(process.cwd(), ".venv", "Scripts", "python3"),
    ]
  : [
      join(process.cwd(), ".venv", "bin", "python3"),
      join(process.cwd(), ".venv", "bin", "python"),
    ];

const fallbackPython = process.platform === "win32" ? "py" : "python3";
const pythonExecutable = pythonCandidates.find((candidate) => existsSync(candidate)) || fallbackPython;

const storageArgs = ["-m", "apps.api.app.scripts.reset_storage"];
if (autoForce) {
  storageArgs.push("--yes");
}

await run(pythonExecutable, storageArgs);
await run("npm", ["run", "clean:force"]);
await run("npm", ["run", "setup"]);
console.log("🔁 reset complete");
