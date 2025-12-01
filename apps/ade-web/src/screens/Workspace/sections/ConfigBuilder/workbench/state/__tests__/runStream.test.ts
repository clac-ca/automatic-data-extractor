import { describe, expect, it } from "vitest";

import type { AdeEvent } from "@shared/runs/types";

import { createRunStreamState, runStreamReducer } from "../runStream";

describe("runStreamReducer", () => {
  it("sets queued status and records run id", () => {
    const state = createRunStreamState(5);
    const event: AdeEvent = {
      type: "run.queued",
      created_at: "2024-01-01T00:00:00Z",
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10",
      payload: { status: "queued" },
    };

    const next = runStreamReducer(state, { type: "EVENT", event });
    expect(next.status).toBe("queued");
    expect(next.runId).toBe("018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10");
    expect(next.consoleLines.length).toBe(1);
  });

  it("moves through build and run lifecycle and clamps console lines", () => {
    const state = createRunStreamState(2);
    const events: AdeEvent[] = [
      { type: "build.started", created_at: "2024-01-01T00:00:01Z", payload: {} },
      { type: "run.started", created_at: "2024-01-01T00:00:02Z", payload: {} },
      {
        type: "run.completed",
        created_at: "2024-01-01T00:00:03Z",
        payload: { status: "succeeded" },
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
    const event: AdeEvent = {
      type: "run.validation.summary",
      created_at: "2024-01-01T00:00:02Z",
      payload: { issues_total: 2, max_severity: "warning" },
    };

    const next = runStreamReducer(state, { type: "EVENT", event });
    expect(next.validationSummary).toEqual(event.payload);
  });
});
