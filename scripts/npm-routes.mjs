import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

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
    child.on("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(stderr || `${command} ${args.join(" ")} exited with code ${code}`));
    });
  });

const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const collectFrontendRoutes = async () => {
  if (!hasFrontend) {
    return { status: "skipped", reason: "frontend missing" };
  }

  const nodeModulesDir = join("frontend", "node_modules");
  if (!existsSync(nodeModulesDir)) {
    return {
      status: "skipped",
      reason: "frontend dependencies not installed",
    };
  }

  const binary = process.platform === "win32" ? "react-router.cmd" : "react-router";
  const localBin = join(nodeModulesDir, ".bin", binary);

  try {
    const { stdout } = existsSync(localBin)
      ? await runCapture(localBin, ["routes", "--json"], {
          cwd: "frontend",
          shell: process.platform === "win32",
        })
      : await runCapture("npx", ["react-router", "routes", "--json"], {
          cwd: "frontend",
          shell: process.platform === "win32",
        });
    const parsed = JSON.parse(stdout);
    const routes = Array.isArray(parsed?.routes) ? parsed.routes : [];
    return { status: "ok", routes, raw: parsed };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { status: "failed", error: message };
  }
};

const result = await collectFrontendRoutes();

if (result.status === "ok") {
  console.log(JSON.stringify({ ok: true, routes: result.routes }, null, 2));
  process.exit(0);
}

const payload = {
  ok: false,
  status: result.status,
  ...(result.reason ? { reason: result.reason } : {}),
  ...(result.error ? { error: result.error } : {}),
};

console.log(JSON.stringify(payload, null, 2));

if (result.status === "failed") {
  process.exit(1);
}
