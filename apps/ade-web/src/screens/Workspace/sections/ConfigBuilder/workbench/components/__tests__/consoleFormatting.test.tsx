import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { formatConsoleLineNdjson, renderConsoleLine } from "../consoleFormatting";
import type { WorkbenchConsoleLine } from "../../types";

describe("renderConsoleLine", () => {
  it("renders plain text message", () => {
    const line: WorkbenchConsoleLine = {
      level: "info",
      message: "hello world",
      origin: "run",
      timestamp: new Date().toISOString(),
    };
    const { container } = render(<div>{renderConsoleLine(line)}</div>);
    expect(container.textContent).toContain("hello world");
  });

  it("renders engine.detector.column_result summary", () => {
    const line: WorkbenchConsoleLine = {
      level: "debug",
      message: "",
      origin: "run",
      timestamp: new Date().toISOString(),
      raw: {
        event: "engine.detector.column_result",
        message: "Column 0 detector detect_email_header executed on NOV 2025",
        data: {
          sheet_name: "NOV 2025",
          column_index: 0,
          detector: { name: "detect_email_header", duration_ms: 1.23, scores: {} },
        },
      },
    };
    const { container } = render(<div>{renderConsoleLine(line)}</div>);
    expect(container.textContent).toContain("Detector");
    expect(container.textContent).toContain("detect_email_header");
    expect(container.textContent).toContain("NOV 2025");
    expect(container.textContent).toContain("col=0");
  });

  it("renders console.line with message", () => {
    const line: WorkbenchConsoleLine = {
      level: "info",
      message: "fallback",
      origin: "build",
      timestamp: new Date().toISOString(),
      raw: {
        event: "console.line",
        message: "",
        data: {
          scope: "build",
          stream: "stdout",
          level: "info",
          message: "Installing collected packages",
        },
      },
    };
    const { container } = render(<div>{renderConsoleLine(line)}</div>);
    expect(container.textContent).toContain("Installing collected packages");
    expect(container.textContent).toContain("scope=build");
  });

  it("formats NDJSON from raw event", () => {
    const line: WorkbenchConsoleLine = {
      level: "debug",
      message: "",
      origin: "run",
      timestamp: new Date().toISOString(),
      raw: { event: "engine.detector.column_result", data: { sheet_name: "S1" } },
    };
    const ndjson = formatConsoleLineNdjson(line);
    expect(ndjson).toContain("\"event\":\"engine.detector.column_result\"");
    expect(ndjson).toContain("\"sheet_name\":\"S1\"");
  });
});
