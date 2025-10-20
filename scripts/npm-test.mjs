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

const backendPresent = existsSync("backend") && existsSync(join("backend", "app"));
const frontendPresent =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

if (backendPresent) {
  const pythonPath =
    process.platform === "win32"
      ? join("backend", ".venv", "Scripts", "python.exe")
      : join("backend", ".venv", "bin", "python3");
  await run(pythonPath, ["-m", "pytest", "-q"], { cwd: "backend" });
}

let frontendHasTests = false;
if (frontendPresent) {
  try {
    const pkg = JSON.parse(await readFile("frontend/package.json", "utf8"));
    frontendHasTests = typeof pkg?.scripts?.test === "string";
  } catch {
    frontendHasTests = false;
  }
}

if (frontendPresent && frontendHasTests) {
  await run("npm", ["--prefix", "frontend", "run", "test"]);
}

console.log("✅ test complete");
