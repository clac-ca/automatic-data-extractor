import { hasBackend, hasFrontend, copyIfExists, run } from "./_helpers.mjs";

if (hasFrontend()) {
  await run("npm", ["--prefix", "frontend", "run", "build"]);
  if (hasBackend()) {
    const copied = await copyIfExists("frontend/build/client", "backend/app/static");
    if (copied) {
      console.log("📦 copied frontend/build/client → backend/app/static");
    }
  }
}

console.log("✅ build complete");
