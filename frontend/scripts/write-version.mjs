import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const publicDir = path.join(projectRoot, "public");
const versionFile = path.join(publicDir, "version.json");

async function main() {
  const envVersion = typeof process.env.ADE_APP_VERSION === "string" ? process.env.ADE_APP_VERSION.trim() : "";
  const version = envVersion || "unknown";

  await mkdir(publicDir, { recursive: true });
  const payload = JSON.stringify({ version }, null, 2);
  await writeFile(versionFile, `${payload}\n`, "utf-8");
  console.log(`Wrote ${path.relative(projectRoot, versionFile)}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
