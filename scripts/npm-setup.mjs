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

const hasBackend = existsSync(join("backend", "app")) && existsSync("pyproject.toml");
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const launcher = process.platform === "win32" ? "py" : "python3";

if (hasBackend) {
  const venvDir = join(process.cwd(), ".venv");
  if (!existsSync(venvDir)) {
    await run(launcher, ["-m", "venv", venvDir]);
  }

  const pythonCandidates = process.platform === "win32"
    ? [
        join(process.cwd(), ".venv", "Scripts", "python.exe"),
        join(process.cwd(), ".venv", "Scripts", "python3.exe"),
      ]
    : [
        join(process.cwd(), ".venv", "bin", "python3"),
        join(process.cwd(), ".venv", "bin", "python"),
      ];
  const pythonExecutable = pythonCandidates.find((candidate) => existsSync(candidate)) || launcher;

  await run(pythonExecutable, ["-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"]);
  await run(pythonExecutable, ["-m", "pip", "install", "-e", ".[dev]"]);
}

if (hasFrontend) {
  await run("npm", ["ci"], { cwd: "frontend" });
}

console.log("✅ setup complete");
