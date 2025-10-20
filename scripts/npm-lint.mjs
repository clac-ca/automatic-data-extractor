import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { readFile } from "node:fs/promises";

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

const scope = process.argv[2];
const validScopes = [undefined, "backend", "frontend", "all"];

if (!validScopes.includes(scope)) {
  console.error(`Unknown lint scope "${scope}". Use "backend", "frontend", or omit for both.`);
  process.exit(1);
}

const shouldRunBackend = scope === undefined || scope === "backend" || scope === "all";
const shouldRunFrontend = scope === undefined || scope === "frontend" || scope === "all";

const backendPresent = existsSync("backend") && existsSync(join("backend", "app"));
const frontendPresent =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

if (shouldRunBackend && !backendPresent) {
  console.warn("⚠️  backend directory missing; skipping backend lint");
}

if (shouldRunFrontend && !frontendPresent) {
  console.warn("⚠️  frontend directory missing; skipping frontend lint");
}

const lintBackend = async () => {
  if (!shouldRunBackend || !backendPresent) return;
  const pythonCandidates = process.platform === "win32"
    ? [
        join(process.cwd(), "backend", ".venv", "Scripts", "python.exe"),
        join(process.cwd(), "backend", ".venv", "Scripts", "python3.exe"),
      ]
    : [
        join(process.cwd(), "backend", ".venv", "bin", "python3"),
        join(process.cwd(), "backend", ".venv", "bin", "python"),
      ];
  const fallback = process.platform === "win32" ? "python" : "python3";
  const pythonExecutable =
    pythonCandidates.find((candidate) => existsSync(candidate)) || fallback;
  await run(pythonExecutable, ["-m", "ruff", "check", "backend/app", "backend/tests"]);
};

const frontendHasLintScript = async () => {
  if (!frontendPresent) return false;
  try {
    const pkg = JSON.parse(await readFile("frontend/package.json", "utf8"));
    return typeof pkg?.scripts?.lint === "string";
  } catch {
    return false;
  }
};

const lintFrontend = async () => {
  if (!shouldRunFrontend || !frontendPresent) return;
  const hasLint = await frontendHasLintScript();
  if (!hasLint) {
    console.warn("⚠️  frontend lint script missing; skipping frontend lint");
    return;
  }
  await run("npm", ["run", "lint"], { cwd: "frontend" });
};

await lintBackend();
await lintFrontend();

console.log("✅ lint complete");
