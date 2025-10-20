import { createInterface } from "node:readline/promises";
import { rm } from "node:fs/promises";
import { stdin as input, stdout as output, env } from "node:process";

const targets = [
  ".venv",
  "backend/app/web/static",
  "frontend/node_modules",
  "frontend/build",
  "frontend/dist",
  "node_modules",
];

const args = process.argv.slice(2);
const lifecycle = env.npm_lifecycle_event ?? "";
const autoForce = lifecycle === "clean:force";
const force =
  autoForce ||
  args.includes("--yes") ||
  args.includes("-y") ||
  args.includes("--force");
const isInteractive = Boolean(input.isTTY && output.isTTY);

if (autoForce) {
  console.log("clean:force detected – running without confirmation.");
}

if (!force) {
  if (!isInteractive) {
    console.log("⚠️ skipping clean; confirmation required. Re-run with --yes to proceed.");
    process.exit(0);
  }

  const rl = createInterface({ input, output });
  console.log("This will remove:");
  for (const target of targets) {
    console.log(`  - ${target}`);
  }
  const answer = (await rl.question("Proceed? [y/N] ")).trim().toLowerCase();
  await rl.close();

  if (answer !== "y" && answer !== "yes") {
    console.log("🛑 clean cancelled");
    process.exit(0);
  }
}

for (const target of targets) {
  await rm(target, { recursive: true, force: true });
}
console.log("🧹 cleaned");
