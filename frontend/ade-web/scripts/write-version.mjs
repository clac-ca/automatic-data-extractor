import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = fileURLToPath(new URL(".", import.meta.url));
const projectRoot = path.resolve(scriptDir, "..");
const packageJsonPath = path.join(projectRoot, "package.json");
const publicDir = path.join(projectRoot, "public");
const versionFile = path.join(publicDir, "version.json");

async function main() {
  const raw = await readFile(packageJsonPath, "utf-8");
  const pkg = JSON.parse(raw);
  const version = typeof pkg.version === "string" && pkg.version.trim() ? pkg.version.trim() : "unknown";

  await mkdir(publicDir, { recursive: true });
  const payload = JSON.stringify({ version }, null, 2);
  await writeFile(versionFile, `${payload}\n`, "utf-8");
  console.log(`Wrote ${path.relative(projectRoot, versionFile)}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
