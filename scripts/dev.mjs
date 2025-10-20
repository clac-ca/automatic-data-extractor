import { hasBackend, hasFrontend, run } from "./_helpers.mjs";

const commands = [];

if (hasBackend()) {
  commands.push('node scripts/run-uvicorn.mjs --host 0.0.0.0 --port 8000 --reload');
}

if (hasFrontend()) {
  commands.push('npm --prefix frontend run dev');
}

if (commands.length === 0) {
  console.log("Nothing to run yet. Add backend/ and/or frontend/ first.");
  process.exit(0);
}

await run("npx", [
  "concurrently",
  "-k",
  "-n",
  "backend,frontend",
  "-c",
  "auto",
  ...commands,
]);
