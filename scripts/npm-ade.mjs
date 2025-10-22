#!/usr/bin/env node

import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { exit, stderr, stdout } from "node:process";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = join(__dirname, "..");
const packageJsonPath = join(projectRoot, "package.json");

const loadScripts = async () => {
  const data = await readFile(packageJsonPath, "utf8");
  const parsed = JSON.parse(data);
  return parsed?.scripts ?? {};
};

const formatScripts = (scripts) => {
  const entries = Object.entries(scripts);
  if (entries.length === 0) return "";
  const maxName = entries.reduce(
    (max, [name]) => Math.max(max, name.length),
    0
  );
  return entries
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, command]) => `  ${name.padEnd(maxName + 2)}${command}`)
    .join("\n");
};

const printHelp = async () => {
  const scripts = await loadScripts();
  stdout.write("Usage: ade <script> [-- <args>]\n");
  stdout.write("Alias for npm run <script>.\n");
  const formatted = formatScripts(scripts);
  if (formatted) {
    stdout.write("\nAvailable scripts:\n");
    stdout.write(`${formatted}\n`);
  } else {
    stdout.write("\nNo npm scripts found in package.json\n");
  }
};

const main = async () => {
  const scripts = await loadScripts();
  const [, , ...argv] = process.argv;
  const [scriptName, ...scriptArgs] = argv;

  if (!scriptName || scriptName === "--help" || scriptName === "-h") {
    await printHelp();
    exit(scriptName ? 0 : 1);
  }

  if (!scripts[scriptName]) {
    stderr.write(`Unknown script "${scriptName}".\n\n`);
    await printHelp();
    exit(1);
  }

  const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
  const npmArgs =
    scriptArgs.length > 0
      ? ["run", scriptName, "--", ...scriptArgs]
      : ["run", scriptName];

  const child = spawn(npmCommand, npmArgs, {
    stdio: "inherit",
    shell: false,
  });

  child.on("error", (error) => {
    stderr.write(`Failed to start npm: ${error.message}\n`);
    exit(1);
  });

  child.on("close", (code) => {
    exit(code ?? 0);
  });
};

main().catch(async (error) => {
  stderr.write(`${error.message}\n`);
  await printHelp();
  exit(1);
});

