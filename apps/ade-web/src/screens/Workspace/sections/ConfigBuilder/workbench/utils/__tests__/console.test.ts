import { describe, expect, it } from "vitest";

import type { AdeEvent } from "@shared/runs/types";

import { describeBuildEvent, describeRunEvent, formatConsoleTimestamp } from "../console";

describe("formatConsoleTimestamp", () => {
  it("formats epoch seconds", () => {
    const label = formatConsoleTimestamp("2024-01-01T00:00:00Z");
    expect(label).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });

  it("handles invalid date", () => {
    expect(formatConsoleTimestamp(new Date("invalid"))).toBe("");
  });
});

describe("describeBuildEvent", () => {
  it("formats build step events", () => {
    const event: AdeEvent = {
      type: "build.phase.started",
      created_at: "2024-01-01T00:00:01Z",
      payload: { phase: "install_engine" },
    };
    const line = describeBuildEvent(event);
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
    const line = describeBuildEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toBe("pip install failed");
  });

  it("marks successful completion as success", () => {
    const event: AdeEvent = {
      type: "build.completed",
      created_at: "2024-01-01T00:00:10Z",
      payload: { status: "succeeded", summary: "ready" },
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toBe("ready");
  });

  it("formats build progress events", () => {
    const event: AdeEvent = {
      type: "build.progress",
      created_at: "2024-01-01T00:00:05Z",
      payload: { step: "create_venv", message: "Creating virtual environment" },
    };
    const line = describeBuildEvent(event);
    expect(line.level).toBe("info");
    expect(line.message).toContain("Creating virtual environment");
  });
});

describe("describeRunEvent", () => {
  it("treats stderr logs as warnings", () => {
    const event: AdeEvent = {
      type: "console.line",
      created_at: "2024-01-01T00:00:20Z",
      payload: { scope: "run", stream: "stderr", level: "warning", message: "warning: detector failed" },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("detector failed");
  });

  it("marks failed completion as error", () => {
    const event: AdeEvent = {
      type: "run.completed",
      created_at: "2024-01-01T00:00:30Z",
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10",
      payload: { status: "failed", execution: { exit_code: 2 }, failure: { message: "Runtime error" } },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Runtime error");
    expect(line.message).toContain("exit code 2");
  });

  it("handles structured summaries without crashing", () => {
    const event: AdeEvent = {
      type: "run.completed",
      created_at: "2024-01-01T00:00:31Z",
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d20",
      payload: { status: "succeeded", summary: { run: { status: "succeeded" } } },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toContain("Run succeeded");
  });

  it("formats telemetry envelopes", () => {
    const event: AdeEvent = {
      type: "run.phase.started",
      created_at: new Date().toISOString(),
      run_id: "018f9c38-0b3f-7c1b-b9f5-5d4c4a8f3d10",
      payload: { phase: "mapping", level: "warning" },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("mapping");
  });

  it("formats waiting_for_build events", () => {
    const event: AdeEvent = {
      type: "run.waiting_for_build",
      created_at: "2024-01-01T00:00:25Z",
      payload: { reason: "build_not_ready", build_id: "bld_123" },
    };
    const line = describeRunEvent(event);
    expect(line.origin).toBe("run");
    expect(line.message).toContain("build_not_ready");
    expect(line.message).toContain("bld_123");
  });

  it("formats run.table.summary with coverage and missing required", () => {
    const event: AdeEvent = {
      type: "run.table.summary",
      created_at: "2025-12-03T21:45:59.474755Z",
      payload: {
        table_id: "tbl_0",
        source_sheet: "Sheet1",
        row_count: 35,
        column_count: 49,
        mapped_column_count: 4,
        unmapped_column_count: 45,
        mapping: {
          mapped_columns: [
            { field: "member_id", is_required: true, is_satisfied: false },
            { field: "email", is_required: true, is_satisfied: false },
            { field: "first_name", is_required: false, is_satisfied: true },
          ],
          unmapped_columns: [
            { header: "Co." },
            { header: "Company Name" },
            { header: "Union Code" },
            { header: "Union Code Description" },
            { header: "Address No." },
          ],
        },
        details: { header_row: 4, first_data_row: 5, last_data_row: 39 },
        source_file: "/path/to/LedcorConstSK_240131.xlsx",
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("35 rows");
    expect(line.message).toContain("49 cols");
    expect(line.message).toContain("mapped 4/49 (8.2%)");
    expect(line.message).toContain("Missing required: member_id, email");
    expect(line.message).toContain("Unmapped: Co., Company Name, Union Code");
    expect(line.message).toContain("header row 4");
  });

  it("formats run.column_detector.score", () => {
    const event: AdeEvent = {
      type: "run.column_detector.score",
      created_at: "2025-12-03T23:05:45.909440Z",
      payload: {
        field: "last_name",
        threshold: 0.5,
        chosen: {
          column_index: 6,
          header: "Last Name",
          score: 0.9,
          passed_threshold: true,
          contributions: [{ detector: "ade_config.column_detectors.last_name.detect_last_name", delta: 0.9 }],
        },
        candidates: [
          { header: "Last Name", score: 0.9, passed_threshold: true },
          { header: "Co.", score: 0.35, passed_threshold: false },
        ],
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("success");
    expect(line.message).toContain("Matched last_name");
    expect(line.message).toContain("Last Name");
    expect(line.message).toContain("0.90");
    expect(line.message).toContain("Top candidates:");
  });

  it("formats run.row_detector.score", () => {
    const event: AdeEvent = {
      type: "run.row_detector.score",
      created_at: "2025-12-03T23:05:45.906917Z",
      payload: {
        thresholds: { header: 0.6, data: 0.5 },
        header_row_index: 4,
        data_row_start_index: 5,
        data_row_end_index: 39,
        trigger: {
          row_index: 4,
          header_score: 1.1,
          data_score: 0.1,
          contributions: [
            { detector: "ade_config.row_detectors.header.detect_known_header_words", scores: { header: 0.6 } },
            { detector: "ade_config.row_detectors.data.detect_mixed_text_and_numbers", scores: { data: 0.1 } },
          ],
          sample: ["Co.", "Company Name"],
        },
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("warning");
    expect(line.message).toContain("header row 4");
    expect(line.message).toContain("data rows 5-39");
    expect(line.message).toContain("hdr");
    expect(line.message).toContain("Sample");
  });

  it("formats run.transform.* events", () => {
    const event: AdeEvent = {
      type: "run.transform.member_id.missing",
      created_at: "2025-12-03T23:12:09.287718Z",
      payload: { row_index: 5 },
    };
    const line = describeRunEvent(event);
    expect(line.message).toContain("Transform: member_id.missing");
    expect(line.message).toContain("row 5");
  });
});
