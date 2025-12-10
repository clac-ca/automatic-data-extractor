import { describe, expect, it } from "vitest";

import type { RunStreamEvent } from "@shared/runs/types";

import { createRunStreamState, runStreamReducer } from "../runStream";

describe("runStreamReducer", () => {
  it("sets queued status and records run id", () => {
    const state = createRunStreamState(5);
    const event: RunStreamEvent = {
      event: "run.queued",
      timestamp: "2024-01-01T00:00:00Z",
      data: { jobId: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10", status: "queued" },
    };

    const next = runStreamReducer(state, { type: "EVENT", event });
    expect(next.status).toBe("queued");
    expect(next.runId).toBe("018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10");
    expect(next.consoleLines.length).toBe(1);
  });

  it("moves through build and run lifecycle and clamps console lines", () => {
    const state = createRunStreamState(2);
    const events: RunStreamEvent[] = [
      { event: "build.start", timestamp: "2024-01-01T00:00:01Z", data: {} },
      { event: "run.start", timestamp: "2024-01-01T00:00:02Z", data: {} },
      {
        event: "run.complete",
        timestamp: "2024-01-01T00:00:03Z",
        data: { status: "succeeded" },
      },
    ];

    const finalState = events.reduce(
      (current, event) => runStreamReducer(current, { type: "EVENT", event }),
      state,
    );

    expect(finalState.status).toBe("succeeded");
    expect(finalState.consoleLines.length).toBe(2);
  });

  it("tracks validation summaries", () => {
    const state = createRunStreamState(3);
    const event: RunStreamEvent = {
      event: "run.validation.summary",
      timestamp: "2024-01-01T00:00:02Z",
      data: { issues_total: 2, max_severity: "warning" },
    };

    const next = runStreamReducer(state, { type: "EVENT", event });
    expect(next.validationSummary).toEqual(event.data);
  });

  it("captures run mode hints from events", () => {
    const state = createRunStreamState(4);
    const event: RunStreamEvent = {
      event: "run.start",
      timestamp: "2024-01-01T00:00:04Z",
      data: { mode: "validation" },
    };

    const next = runStreamReducer(state, { type: "EVENT", event });
    expect(next.runMode).toBe("validation");
  });
});
