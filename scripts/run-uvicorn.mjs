import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { join } from "node:path";

const args = ["app.main:app", ...process.argv.slice(2)];

const candidates = [
  process.platform === "win32"
    ? join("backend", ".venv", "Scripts", "uvicorn.exe")
    : join("backend", ".venv", "bin", "uvicorn"),
  "uvicorn",
];

const executable = candidates.find((candidate) => existsSync(candidate) || candidate === "uvicorn");

if (!executable) {
  console.error("Unable to find uvicorn. Run `npm run setup` first.");
  process.exit(1);
}

const child = spawn(executable, args, {
  cwd: "backend",
  stdio: "inherit",
  shell: executable === "uvicorn",
});

child.on("close", (code) => {
  process.exit(code ?? 0);
});
