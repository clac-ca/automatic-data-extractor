import { describe, expect, it } from "vitest";

import type { AdeEvent } from "@shared/runs/types";

import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "../console";

describe("formatConsoleTimestamp", () => {
  it("formats epoch seconds", () => {
    const label = formatConsoleTimestamp(1_700_000_000);
    expect(label).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });

  it("handles invalid date", () => {
    expect(formatConsoleTimestamp(new Date("invalid"))).toBe("");
  });
});

describe("describeBuildEvent", () => {
  it("formats build step events", () => {
    const event: AdeEvent = {
      object: "ade.event",
      type: "build.progress",
      created_at: "2024-01-01T00:00:01Z",
      build: { phase: "install_engine" },
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.message).toContain("install_engine");
  });

  it("promotes stderr logs to warnings", () => {
    const event: AdeEvent = {
      object: "ade.event",
      type: "build.log.delta",
      created_at: "2024-01-01T00:00:02Z",
      log: { stream: "stderr", message: "pip install failed" },
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toBe("pip install failed");
  });

  it("marks successful completion as success", () => {
    const event: AdeEvent = {
      object: "ade.event",
      type: "build.completed",
      created_at: "2024-01-01T00:00:10Z",
      build_id: "build_123",
      build: { status: "active", exit_code: 0, error_message: null, summary: "ready" },
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toBe("ready");
  });
});

describe("describeRunEvent", () => {
  it("treats stderr logs as warnings", () => {
    const event: AdeEvent = {
      object: "ade.event",
      type: "run.log.delta",
      created_at: "2024-01-01T00:00:20Z",
      log: { stream: "stderr", message: "warning: detector failed" },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("detector failed");
  });

  it("marks failed completion as error", () => {
    const event: AdeEvent = {
      object: "ade.event",
      type: "run.completed",
      created_at: "2024-01-01T00:00:30Z",
      run_id: "run_123",
      run: { status: "failed", execution_summary: { exit_code: 2 }, error_message: "Runtime error" },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Runtime error");
    expect(line.message).toContain("exit code 2");
  });

  it("formats telemetry envelopes", () => {
    const event: AdeEvent = {
      object: "ade.event",
      type: "run.pipeline.progress",
      created_at: new Date().toISOString(),
      run_id: "run_123",
      run: { phase: "mapping", level: "warning" },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("mapping");
  });
});
