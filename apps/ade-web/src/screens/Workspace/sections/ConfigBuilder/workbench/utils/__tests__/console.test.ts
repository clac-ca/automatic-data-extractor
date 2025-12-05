import { describe, expect, it } from "vitest";

import type { AdeEvent } from "@shared/runs/types";

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
    const event: AdeEvent = {
      type: "build.phase.start",
      created_at: "2024-01-01T00:00:01Z",
      payload: { phase: "install_engine" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.origin).toBe("build");
    expect(line.message).toContain("install_engine");
  });

  it("promotes stderr logs to warnings", () => {
    const event: AdeEvent = {
      type: "console.line",
      created_at: "2024-01-01T00:00:02Z",
      payload: { scope: "build", stream: "stderr", message: "pip install failed" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toBe("pip install failed");
  });

  it("marks successful completion as success", () => {
    const event: AdeEvent = {
      type: "build.complete",
      created_at: "2024-01-01T00:00:10Z",
      payload: { status: "succeeded", summary: "ready" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toBe("ready");
  });

  it("formats build progress events", () => {
    const event: AdeEvent = {
      type: "build.progress",
      created_at: "2024-01-01T00:00:05Z",
      payload: { step: "create_venv", message: "Creating virtual environment" },
    };
    const line = formatBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.message).toContain("Creating virtual environment");
  });
});

describe("formatRunEvent", () => {
  it("treats stderr logs as warnings", () => {
    const event: AdeEvent = {
      type: "console.line",
      created_at: "2024-01-01T00:00:20Z",
      payload: { scope: "run", stream: "stderr", level: "warning", message: "warning: detector failed" },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("detector failed");
  });

  it("marks failed completion as error", () => {
    const event: AdeEvent = {
      type: "run.complete",
      created_at: "2024-01-01T00:00:30Z",
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10",
      payload: { status: "failed", execution: { exit_code: 2 }, failure: { message: "Runtime error" } },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Runtime error");
    expect(line.message).toContain("exit code 2");
  });

  it("handles structured summaries without crashing", () => {
    const event: AdeEvent = {
      type: "run.complete",
      created_at: "2024-01-01T00:00:31Z",
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d20",
      payload: { status: "succeeded", summary: { run: { status: "succeeded" } } },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toContain("Run succeeded");
  });

  it("formats telemetry envelopes", () => {
    const event: AdeEvent = {
      type: "engine.phase.start",
      created_at: new Date().toISOString(),
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10",
      payload: { phase: "mapping", level: "warning" },
    };
    const line = formatRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("mapping");
  });

  it("formats waiting_for_build events", () => {
    const event: AdeEvent = {
      type: "run.waiting_for_build",
      created_at: "2024-01-01T00:00:25Z",
      payload: { reason: "build_not_ready", build_id: "bld_123" },
    };
    const line = formatRunEvent(event);
    expect(line.origin).toBe("run");
    expect(line.message).toContain("build_not_ready");
    expect(line.message).toContain("bld_123");
  });
});
