import { existsSync } from "node:fs";
import { join } from "node:path";
import {
  hasBackend,
  hasFrontend,
  run,
  commandExists,
  backendPythonPath,
} from "./_helpers.mjs";

const launcher = process.platform === "win32" ? "py" : "python3";

if (hasBackend()) {
  const venvDir = join("backend", ".venv");
  if (!existsSync(venvDir)) {
    await run(launcher, ["-m", "venv", venvDir]);
  }

  const pythonPath = backendPythonPath();
  const uvLockExists = existsSync("backend/uv.lock");
  const uvAvailable = await commandExists("uv");

  if (uvAvailable && uvLockExists) {
    await run("uv", ["pip", "sync", "--python", pythonPath, "--from", "backend/uv.lock"]);
  } else {
    await run(pythonPath, ["-m", "pip", "install", "--upgrade", "pip"]);
    await run(pythonPath, ["-m", "pip", "install", "--upgrade", "setuptools", "wheel"]);
    await run(pythonPath, ["-m", "pip", "install", "-e", "."], { cwd: "backend" });
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
    await run(pythonPath, ["-c", extractDevDeps], { cwd: "backend" });
  }
}

if (hasFrontend()) {
  await run("npm", ["--prefix", "frontend", "ci"]);
}

console.log("✅ setup complete");
