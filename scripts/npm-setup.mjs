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

const commandExists = (command) =>
  new Promise((resolve) => {
    const checker = process.platform === "win32" ? "where" : "which";
    const child = spawn(checker, [command], {
      stdio: "ignore",
      shell: false,
    });
    child.on("close", (code) => resolve(code === 0));
    child.on("error", () => resolve(false));
  });

const hasBackend = existsSync("backend") && existsSync(join("backend", "app"));
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const launcher = process.platform === "win32" ? "py" : "python3";

if (hasBackend) {
  const venvDir = join("backend", ".venv");
  if (!existsSync(venvDir)) {
    await run(launcher, ["-m", "venv", venvDir]);
  }

  const pythonPath =
    process.platform === "win32"
      ? join(process.cwd(), "backend", ".venv", "Scripts", "python.exe")
      : join(process.cwd(), "backend", ".venv", "bin", "python3");
  const pythonFallback =
    process.platform === "win32"
      ? join(process.cwd(), "backend", ".venv", "Scripts", "python.exe")
      : join(process.cwd(), "backend", ".venv", "bin", "python");
  const pythonExecutable = existsSync(pythonPath)
    ? pythonPath
    : existsSync(pythonFallback)
      ? pythonFallback
      : pythonPath;
  const uvLockExists = existsSync("backend/uv.lock");
  const uvAvailable = await commandExists("uv");

  if (uvAvailable && uvLockExists) {
    await run("uv", ["pip", "sync", "--python", pythonExecutable, "--from", "backend/uv.lock"]);
  } else {
    await run(pythonExecutable, ["-m", "pip", "install", "--upgrade", "pip"]);
    await run(pythonExecutable, ["-m", "pip", "install", "--upgrade", "setuptools", "wheel"]);
    await run(pythonExecutable, ["-m", "pip", "install", "-e", "."], { cwd: "backend" });
    const extractDevDeps = `
import subprocess
import sys
from pathlib import Path
try:
    import tomllib
except ImportError:
    import tomli as tomllib

pyproject = Path("pyproject.toml")
if not pyproject.is_file():
    sys.exit(0)

data = tomllib.loads(pyproject.read_text("utf-8"))
dev_deps = data.get("tool", {}).get("uv", {}).get("dev-dependencies", [])
if dev_deps:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *dev_deps])
`;
    await run(pythonExecutable, ["-c", extractDevDeps], { cwd: "backend" });
  }
}

if (hasFrontend) {
  await run("npm", ["ci"], { cwd: "frontend" });
}

console.log("✅ setup complete");
