import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
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

const hasBackend =
  existsSync(join("apps", "api", "app")) &&
  existsSync(join("apps", "api", "pyproject.toml"));
const hasFrontend =
  existsSync(join("apps", "web")) && existsSync(join("apps", "web", "package.json"));

if (!hasBackend) {
  console.log("⏭️  backend missing; skipping OpenAPI generation");
  process.exit(0);
}

const pythonPathCandidates = process.platform === "win32"
  ? [
      join(process.cwd(), ".venv", "Scripts", "python.exe"),
      join(process.cwd(), ".venv", "Scripts", "python3.exe"),
    ]
  : [
      join(process.cwd(), ".venv", "bin", "python3"),
      join(process.cwd(), ".venv", "bin", "python"),
    ];

const pythonExecutable =
  pythonPathCandidates.find((candidate) => existsSync(candidate)) ??
  (process.platform === "win32" ? "python" : "python3");

if (!pythonExecutable) {
  console.error(
    "❌ unable to locate backend virtualenv python; run `npm run setup` first.",
  );
  process.exit(1);
}

const openapiRelativePath = join("apps", "api", "app", "openapi.json");
const openapiPath = openapiRelativePath;
const outputPath = join("apps", "web", "src", "generated", "openapi.d.ts");

await run(
  pythonExecutable,
  ["-m", "apps.api.app.scripts.generate_openapi", "--output", openapiRelativePath],
  { cwd: process.cwd() },
);

if (!hasFrontend) {
  console.log("ℹ️  frontend missing; OpenAPI JSON generated but skipping types.");
  process.exit(0);
}

const generatedDir = join("apps", "web", "src", "generated");
if (!existsSync(generatedDir)) {
  mkdirSync(generatedDir, { recursive: true });
}

const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";

await run(npxCommand, ["openapi-typescript", openapiPath, "--output", outputPath, "--export-type"]);

console.log("✅ generated apps/web/src/generated/openapi.d.ts");
