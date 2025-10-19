import { readFile } from "node:fs/promises";
import {
  hasBackend,
  hasFrontend,
  run,
  backendPythonPath,
} from "./_helpers.mjs";

if (hasBackend()) {
  await run(backendPythonPath(), ["-m", "pytest", "-q"], { cwd: "backend" });
}

let frontendHasTests = false;
if (hasFrontend()) {
  try {
    const pkg = JSON.parse(await readFile("frontend/package.json", "utf8"));
    frontendHasTests = typeof pkg?.scripts?.test === "string";
  } catch {
    frontendHasTests = false;
  }
}

if (hasFrontend() && frontendHasTests) {
  await run("npm", ["--prefix", "frontend", "run", "test"]);
}

console.log("✅ test complete");
