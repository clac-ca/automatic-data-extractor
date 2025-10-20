import { createInterface } from "node:readline/promises";
import { spawn } from "node:child_process";
import { rm } from "node:fs/promises";
import { stdin as input, stdout as output, env } from "node:process";

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

const lifecycle = env.npm_lifecycle_event ?? "";
const autoForce = lifecycle === "reset:force";
const isInteractive = Boolean(input.isTTY && output.isTTY);

if (autoForce) {
  console.log("reset:force detected – running without confirmation.");
}

if (!autoForce) {
  if (!isInteractive) {
    console.log("⚠️ skipping reset; confirmation required. Use `npm run reset:force` to proceed non-interactively.");
    process.exit(0);
  }

  const rl = createInterface({ input, output });
  console.log("This will:");
  console.log("  - Remove build artifacts and dependencies");
  console.log("  - Delete the ./data directory");
  console.log("  - Reinstall backend/frontend requirements");
  const answer = (await rl.question("Proceed? [y/N] ")).trim().toLowerCase();
  await rl.close();

  if (answer !== "y" && answer !== "yes") {
    console.log("🛑 reset cancelled");
    process.exit(0);
  }
}

console.log("Removing ./data directory...");
await rm("data", { recursive: true, force: true });
await run("npm", ["run", "clean:force"]);
await run("npm", ["run", "setup"]);
console.log("🔁 reset complete");
