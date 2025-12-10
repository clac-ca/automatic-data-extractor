import { describe, expect, it } from "vitest";

import type { RunStreamEvent } from "@shared/runs/types";

import { formatBuildEvent, formatConsoleTimestamp, formatRunEvent } from "../../events/format";

describe("formatConsoleTimestamp", () => {
  it("formats epoch seconds", () => {
    const label = formatConsoleTimestamp("2024-01-01T00:00:00Z");
    expect(label).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });

  it("handles invalid date", () => {
    expect(formatConsoleTimestamp(new Date("invalid"))).toBe("");
  });
});

describe("formatBuildEvent", () => {
  it("formats build step events", () => {
    const event: RunStreamEvent = {
      event: "build.phase.start",
      timestamp: "2024-01-01T00:00:01Z",
      data: { phase: "install_engine" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.origin).toBe("build");
    expect(line.message).toContain("install_engine");
  });

  it("promotes stderr logs to warnings", () => {
    const event: RunStreamEvent = {
      event: "console.line",
      timestamp: "2024-01-01T00:00:02Z",
      data: { scope: "build", stream: "stderr", message: "pip install failed" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toBe("pip install failed");
  });

  it("marks successful completion as success", () => {
    const event: RunStreamEvent = {
      event: "build.complete",
      timestamp: "2024-01-01T00:00:10Z",
      data: { status: "succeeded", summary: "ready" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toBe("ready");
  });

  it("formats build progress events", () => {
    const event: RunStreamEvent = {
      event: "build.progress",
      timestamp: "2024-01-01T00:00:05Z",
      data: { step: "create_venv", message: "Creating virtual environment" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.message).toContain("Creating virtual environment");
  });
});

describe("formatRunEvent", () => {
  it("treats stderr logs as warnings", () => {
    const event: RunStreamEvent = {
      event: "console.line",
      timestamp: "2024-01-01T00:00:20Z",
      data: { scope: "run", stream: "stderr", level: "warning", message: "warning: detector failed" },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("detector failed");
  });

  it("marks failed completion as error", () => {
    const event: RunStreamEvent = {
      event: "run.complete",
      timestamp: "2024-01-01T00:00:30Z",
      data: { status: "failed", execution: { exit_code: 2 }, failure: { message: "Runtime error" } },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Runtime error");
    expect(line.message).toContain("exit code 2");
  });

  it("handles structured summaries without crashing", () => {
    const event: RunStreamEvent = {
      event: "run.complete",
      timestamp: "2024-01-01T00:00:31Z",
      data: { status: "succeeded", summary: { run: { status: "succeeded" } } },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toContain("Run succeeded");
  });

  it("formats telemetry envelopes", () => {
    const event: RunStreamEvent = {
      event: "engine.phase.start",
      timestamp: new Date().toISOString(),
      data: { phase: "mapping", level: "warning" },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("mapping");
  });

  it("formats waiting_for_build events", () => {
    const event: RunStreamEvent = {
      event: "run.waiting_for_build",
      timestamp: "2024-01-01T00:00:25Z",
      data: { reason: "build_not_ready", build_id: "bld_123" },
    };
    const line = formatRunEvent(event);
    expect(line.origin).toBe("run");
    expect(line.message).toContain("build_not_ready");
    expect(line.message).toContain("bld_123");
  });
});
