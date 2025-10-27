import { spawn } from "node:child_process";

const runCapture = (command, args = [], options = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: ["ignore", "pipe", "pipe"],
      shell: false,
      ...options,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      reject(error);
    });
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else
        reject(
          new Error(
            stderr || `${command} ${args.join(" ")} exited with code ${code}`,
          ),
        );
    });
  });

const pythonCandidates = [
  process.env.ADE_PYTHON,
  process.platform === "win32" ? "python" : "python3",
  process.platform === "win32" ? "python3" : "python",
].filter(Boolean);

const moduleArgs = ["-m", "backend.app.scripts.api_routes", ...process.argv.slice(2)];
let lastError;
for (const command of pythonCandidates) {
  try {
    const { stdout } = await runCapture(command, moduleArgs);
    process.stdout.write(stdout);
    process.exit(0);
  } catch (error) {
    lastError = error instanceof Error ? error : new Error(String(error));
  }
}

const fallback = {
  ok: false,
  error: lastError ? lastError.message : "Unable to execute python interpreter",
};
console.error(JSON.stringify(fallback, null, 2));
process.exit(1);
