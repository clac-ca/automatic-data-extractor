import { collectFrontendRoutes } from "./_helpers.mjs";

const result = await collectFrontendRoutes();

if (result.status === "ok") {
  console.log(JSON.stringify({ ok: true, routes: result.routes }, null, 2));
  process.exit(0);
}

const payload = {
  ok: false,
  status: result.status,
  ...(result.reason ? { reason: result.reason } : {}),
  ...(result.error ? { error: result.error } : {}),
};

console.log(JSON.stringify(payload, null, 2));

if (result.status === "failed") {
  process.exit(1);
}
