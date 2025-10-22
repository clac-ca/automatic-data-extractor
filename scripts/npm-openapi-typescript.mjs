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

const hasBackend = existsSync(join("backend", "app")) && existsSync("pyproject.toml");
const hasFrontend =
  existsSync("frontend") && existsSync(join("frontend", "package.json"));

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

const openapiRelativePath = join("backend", "app", "openapi.json");
const openapiPath = openapiRelativePath;
const outputPath = join("frontend", "src", "generated", "openapi.d.ts");

await run(
  pythonExecutable,
  [
    "-c",
    [
      "import json",
      "from pathlib import Path",
      "from backend.app.main import create_app",
      "app = create_app()",
      "schema = app.openapi()",
      `Path(r"${openapiRelativePath}").write_text(json.dumps(schema, indent=2))`,
      `print('📝 wrote ${openapiRelativePath}')`,
    ].join("; "),
  ],
  { cwd: process.cwd() },
);

if (!hasFrontend) {
  console.log("ℹ️  frontend missing; OpenAPI JSON generated but skipping types.");
  process.exit(0);
}

const generatedDir = join("frontend", "src", "generated");
if (!existsSync(generatedDir)) {
  mkdirSync(generatedDir, { recursive: true });
}

const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";

await run(npxCommand, ["openapi-typescript", openapiPath, "--output", outputPath, "--export-type"]);

console.log("✅ generated frontend/src/generated/openapi.d.ts");
