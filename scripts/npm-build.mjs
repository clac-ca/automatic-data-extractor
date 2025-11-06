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

const hasBackend = existsSync(join("apps", "api", "app")) && existsSync("pyproject.toml");
const hasFrontend =
  existsSync(join("apps", "web")) && existsSync(join("apps", "web", "package.json"));

const copyIfExists = async (from, to) => {
  if (!existsSync(from)) return false;
  await cp(from, to, { recursive: true });
  return true;
};

if (hasFrontend) {
  await run("npm", ["run", "build"], { cwd: join("apps", "web") });
  if (hasBackend) {
    const copied = await copyIfExists(
      join("apps", "web", "build", "client"),
      join("apps", "api", "app", "web", "static"),
    );
    if (copied) {
      console.log("📦 copied apps/web/build/client → apps/api/app/web/static");
    }
  }
}

console.log("✅ build complete");
