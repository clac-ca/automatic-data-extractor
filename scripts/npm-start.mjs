import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, "..");
const backendDir = join(projectRoot, "backend");
const venvUvicorn =
  process.platform === "win32"
    ? join(backendDir, ".venv", "Scripts", "uvicorn.exe")
    : join(backendDir, ".venv", "bin", "uvicorn");

const command = existsSync(venvUvicorn) ? venvUvicorn : "uvicorn";
const args = ["app.main:app", "--host", "0.0.0.0", "--port", "8000"];

const child = spawn(command, args, {
  cwd: backendDir,
  stdio: "inherit",
  shell: command === "uvicorn",
});

child.on("error", (error) => {
  console.error("Unable to start uvicorn. Did you run `npm run setup`?", error);
  process.exit(1);
});

child.on("close", (code) => {
  process.exit(code ?? 0);
});
