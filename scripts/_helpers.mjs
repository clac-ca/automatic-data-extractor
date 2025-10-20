import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { cp, rm } from "node:fs/promises";
import { join } from "node:path";

export const hasBackend = () => existsSync("backend") && existsSync("backend/app");
export const hasFrontend = () => existsSync("frontend") && existsSync("frontend/package.json");

export const run = (cmd, args = [], opts = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: "inherit", shell: false, ...opts });
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${cmd} ${args.join(" ")} exited with code ${code}`));
    });
  });

export const runCap = (cmd, args = [], opts = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"], shell: false, ...opts });
    let out = "";
    let err = "";
    child.stdout.on("data", (chunk) => {
      out += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      err += chunk.toString();
    });
    child.on("close", (code) => {
      if (code === 0) resolve({ out, err });
      else reject(new Error(err || `${cmd} ${args.join(" ")} exited with code ${code}`));
    });
  });

export const commandExists = async (command) => {
  try {
    if (process.platform === "win32") {
      await runCap("where", [command]);
    } else {
      await runCap("which", [command]);
    }
    return true;
  } catch {
    return false;
  }
};

export const copyIfExists = async (from, to) => {
  if (!existsSync(from)) return false;
  await cp(from, to, { recursive: true });
  return true;
};

export const cleanPaths = async (paths) => {
  for (const path of paths) {
    await rm(path, { recursive: true, force: true });
  }
};

export const backendVenvPath = (subpath) => {
  const base = process.platform === "win32" ? ["backend", ".venv", "Scripts"] : ["backend", ".venv", "bin"];
  return join(process.cwd(), ...base, subpath);
};

export const backendPythonPath = () =>
  process.platform === "win32"
    ? backendVenvPath("python.exe")
    : existsSync(backendVenvPath("python3"))
      ? backendVenvPath("python3")
      : backendVenvPath("python");

export const collectFrontendRoutes = async () => {
  if (!hasFrontend()) {
    return { status: "skipped", reason: "frontend missing" };
  }

  const nodeModulesDir = join("frontend", "node_modules");
  if (!existsSync(nodeModulesDir)) {
    return { status: "skipped", reason: "frontend dependencies not installed" };
  }

  const binary = process.platform === "win32" ? "react-router.cmd" : "react-router";
  const localBin = join(nodeModulesDir, ".bin", binary);

  try {
    let out;
    if (existsSync(localBin)) {
      ({ out } = await runCap(localBin, ["routes", "--json"], {
        cwd: "frontend",
        shell: process.platform === "win32",
      }));
    } else {
      ({ out } = await runCap("npx", ["react-router", "routes", "--json"], {
        cwd: "frontend",
        shell: process.platform === "win32",
      }));
    }
    const parsed = JSON.parse(out);
    const routes = Array.isArray(parsed?.routes) ? parsed.routes : [];
    return { status: "ok", routes, raw: parsed };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { status: "failed", error: message };
  }
};
