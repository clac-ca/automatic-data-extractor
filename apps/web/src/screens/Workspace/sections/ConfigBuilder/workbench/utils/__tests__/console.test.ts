import { describe, expect, it } from "vitest";

import type { BuildCompletedEvent, BuildLogEvent, BuildStepEvent } from "@shared/builds/types";
import type { RunCompletedEvent, RunLogEvent } from "@shared/runs/types";

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
    const event: BuildStepEvent = {
      object: "ade.build.event",
      build_id: "build_123",
      created: 1_700_000_001,
      type: "build.step",
      step: "install_engine",
      message: null,
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.message).toContain("ade_engine");
  });

  it("promotes stderr logs to warnings", () => {
    const event: BuildLogEvent = {
      object: "ade.build.event",
      build_id: "build_123",
      created: 1_700_000_002,
      type: "build.log",
      stream: "stderr",
      message: "pip install failed",
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toBe("pip install failed");
  });

  it("marks successful completion as success", () => {
    const event: BuildCompletedEvent = {
      object: "ade.build.event",
      build_id: "build_123",
      created: 1_700_000_010,
      type: "build.completed",
      status: "active",
      exit_code: 0,
      error_message: null,
      summary: "ready",
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toBe("ready");
  });
});

describe("describeRunEvent", () => {
  it("treats stderr logs as warnings", () => {
    const event: RunLogEvent = {
      object: "ade.run.event",
      run_id: "run_123",
      created: 1_700_000_020,
      type: "run.log",
      stream: "stderr",
      message: "warning: detector failed",
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("detector failed");
  });

  it("marks failed completion as error", () => {
    const event: RunCompletedEvent = {
      object: "ade.run.event",
      run_id: "run_123",
      created: 1_700_000_030,
      type: "run.completed",
      status: "failed",
      exit_code: 2,
      error_message: "Runtime error",
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Runtime error");
    expect(line.message).toContain("exit code 2");
  });
});
