import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { cp } from "node:fs/promises";
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

const hasBackend = existsSync("backend") && existsSync(join("backend", "app"));
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

const copyIfExists = async (from, to) => {
  if (!existsSync(from)) return false;
  await cp(from, to, { recursive: true });
  return true;
};

if (hasFrontend) {
  await run("npm", ["--prefix", "frontend", "run", "build"]);
  if (hasBackend) {
    const copied = await copyIfExists(
      join("frontend", "build", "client"),
      join("backend", "app", "static"),
    );
    if (copied) {
      console.log("📦 copied frontend/build/client → backend/app/static");
    }
  }
}

console.log("✅ build complete");
