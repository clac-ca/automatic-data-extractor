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
      type: "build.phase.start",
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
      type: "build.complete",
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
      type: "run.complete",
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
      type: "run.complete",
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
      type: "engine.phase.start",
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
      type: "engine.table.summary",
      created_at: "2025-12-03T21:45:59.474755Z",
      payload: {
        schema_id: "ade.summary",
        scope: "table",
        id: "tbl_0",
        source: { sheet_name: "Sheet1", file_path: "/tmp/input.xlsx", table_index: 0, output_sheet: "Normalized" },
        counts: {
          rows: { total: 10 },
          columns: { physical_total: 5, distinct_headers: 5, distinct_headers_mapped: 2 },
          fields: { total: 3, required: 1, mapped: 2, required_unmapped: 1 },
        },
        fields: [
          { field: "first_name", required: false, mapped: true },
          { field: "email", required: true, mapped: false },
          { field: "last_name", required: false, mapped: true },
        ],
        columns: [
          { header: "H1", mapped: false },
          { header: "H2", mapped: false },
          { header: "Mapped", mapped: true },
        ],
        details: { header_row_index: 4, first_data_row_index: 5, last_data_row_index: 14 },
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Table summary");
    expect(line.message).toContain("Sheet1");
    expect(line.message).toContain("table 0");
    expect(line.message).toContain("rows 10");
    expect(line.message).toContain("cols 5");
    expect(line.message).toContain("mapped fields 2/3");
    expect(line.message).toContain("required missing 1/1");
    expect(line.message).toContain("headers mapped 2/5");
    expect(line.message).toContain("Unmapped headers: H1, H2");
    expect(line.message).toContain("Unmapped fields: email");
  });

  it("formats engine.detector.column.score", () => {
    const event: AdeEvent = {
      type: "engine.detector.column.score",
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

  it("formats engine.detector.row.score", () => {
    const event: AdeEvent = {
      type: "engine.detector.row.score",
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

  it("formats config.* events", () => {
    const event: AdeEvent = {
      type: "config.hook.run_completed",
      created_at: "2025-12-04T01:47:17.683286Z",
      payload: {
        stage: "on_run_end",
        status: "RunStatus.SUCCEEDED",
        outputs: ["/tmp/output.xlsx"],
        note: "custom",
      },
    };
    const line = describeRunEvent(event);
    expect(line.message).toContain("Config event: hook.run_completed");
    expect(line.message).toContain('"stage": "on_run_end"');
    expect(line.message).toContain('"status": "RunStatus.SUCCEEDED"');
    expect(line.message).toContain('"/tmp/output.xlsx"');
    expect(line.message).toContain('"note": "custom"');
  });

  it("formats engine.file.summary", () => {
    const event: AdeEvent = {
      type: "engine.file.summary",
      created_at: "2025-12-04T02:40:53.781244Z",
      payload: {
        source: { file_path: "/tmp/input.xlsx" },
        counts: {
          sheets: { total: 1 },
          tables: { total: 1 },
          rows: { total: 128 },
          columns: { physical_total: 48, distinct_headers: 48, distinct_headers_mapped: 3 },
          fields: { total: 3, required: 1, mapped: 2, required_unmapped: 1 },
        },
        fields: [
          { field: "first_name", required: false, mapped: true },
          { field: "last_name", required: false, mapped: true },
          { field: "email", required: true, mapped: false },
        ],
        columns: [
          { header: "Company Name", mapped: false },
          { header: "Union Code", mapped: false },
        ],
        details: { sheet_ids: ["sheet_0"], table_ids: ["tbl_0"] },
        id: "file_0",
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("File summary");
    expect(line.message).toContain("rows 128");
    expect(line.message).toContain("cols 48");
    expect(line.message).toContain("mapped fields 2/3");
    expect(line.message).toContain("required missing 1/1");
    expect(line.message).toContain("Unmapped headers");
    expect(line.message).toContain("Company Name");
    expect(line.message).toContain("Union Code");
    expect(line.message).toContain("email");
  });

  it("formats ade.summary run scope payloads", () => {
    const event: AdeEvent = {
      type: "engine.run.summary",
      created_at: "2025-12-04T03:00:27.822528Z",
      payload: {
        schema_id: "ade.summary",
        schema_version: "1.0.0",
        scope: "run",
        source: {
          status: "failed",
          failure: {
            code: "unknown_error",
            stage: "extracting",
            message: "Missing required keyword-only arguments",
          },
        },
        counts: {
          files: { total: 0 },
          tables: { total: 0 },
          rows: { total: 0 },
          columns: { physical_total: 0 },
          fields: { total: 3, required: 1, mapped: 0, required_unmapped: 1 },
        },
        fields: [
          { field: "first_name", required: false, mapped: false },
          { field: "last_name", required: false, mapped: false },
          { field: "email", required: true, mapped: false },
        ],
        details: { output_paths: [], processed_files: [] },
      },
    };
    const line = describeRunEvent(event);
    expect(line.level).toBe("error");
    expect(line.message).toContain("Run summary");
    expect(line.message).toContain("failed");
    expect(line.message).toContain("required missing 1/1");
    expect(line.message).toContain("Unmapped fields: first_name, last_name, email");
    expect(line.message).toContain("Missing required keyword-only arguments");
  });
});
