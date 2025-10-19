import { run } from "./_helpers.mjs";

await run("node", ["scripts/run-uvicorn.mjs", "--host", "0.0.0.0", "--port", "8000"]);
