import type { WorkbenchConsoleLine } from "../types";
import type { ReactElement } from "react";

export function resolveSeverity(level: WorkbenchConsoleLine["level"] | "all"): number {
  if (level === "debug") return 0;
  if (level === "error") return 3;
  if (level === "warning") return 2;
  if (level === "success") return 1;
  if (level === "info") return 1;
  return 0;
}

export function renderConsoleLine(line: WorkbenchConsoleLine) {
  const raw = line.raw;
  if (raw && typeof raw === "object") {
    const formatted = formatEventRecord(raw as Record<string, unknown>);
    if (formatted) {
      return formatted;
    }
  }

  return renderPlainText(line.message);
}

export function formatConsoleLineNdjson(line: WorkbenchConsoleLine): string | null {
  const raw = line.raw;
  if (!raw || typeof raw !== "object") {
    return null;
  }
  try {
    return JSON.stringify(raw);
  } catch {
    return null;
  }
}

function safeParseJson(value: string) {
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

function renderPlainText(message: string) {
  if (message.includes("\n")) {
    const lines = message.split(/\r?\n/);
    const [firstLine, ...rest] = lines;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{firstLine || " "}</span>
        {rest.length > 0 ? (
          <pre className="whitespace-pre-wrap break-words border-l border-[#2f2f2f] pl-3 text-[12px] leading-snug text-[#9da5b4]">
            {rest.join("\n")}
          </pre>
        ) : null}
      </div>
    );
  }

  const parsed = safeParseJson(message);
  if (!parsed) {
    return message;
  }

  const pretty = JSON.stringify(parsed, null, 2);
  return (
    <pre className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-[#d4d4d4]">
      {highlightJson(pretty)}
    </pre>
  );
}

function highlightJson(text: string) {
  const regex =
    /("(?:\\.|[^"])*"(?=:)|"(?:\\.|[^"])*")|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|\b(true|false|null)\b/g;
  const parts: Array<string | ReactElement> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const className = match[1]
      ? "text-sky-300"
      : match[2]
        ? "text-amber-300"
        : "text-rose-300";
    parts.push(
      <span key={`json-${key++}`} className={className}>
        {token}
      </span>,
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
}

function formatEventRecord(event: Record<string, unknown>) {
  const name = typeof event.event === "string" ? event.event : typeof event.type === "string" ? event.type : "";
  if (!name) return null;

  const message = typeof event.message === "string" ? event.message : "";
  const data = event.data && typeof event.data === "object" ? (event.data as Record<string, unknown>) : {};

  if (name === "console.line") {
    const scope = typeof data.scope === "string" ? data.scope : undefined;
    const stream = typeof data.stream === "string" ? data.stream : undefined;
    const level = typeof data.level === "string" ? data.level : undefined;
    const text = typeof data.message === "string" ? data.message : message;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{text || " "}</span>
        {scope || stream || level ? (
          <span className="text-[11px] text-slate-500">
            {scope ? `scope=${scope} ` : ""}
            {stream ? `stream=${stream} ` : ""}
            {level ? `level=${level}` : ""}
          </span>
        ) : null}
      </div>
    );
  }

  if (name === "engine.config.loaded") {
    const pkg = typeof data.config_package === "string" ? data.config_package : undefined;
    const entry = typeof data.entrypoint === "string" ? data.entrypoint : undefined;
    const fields = Array.isArray(data.fields) ? data.fields.length : undefined;
    const settings = data.settings && typeof data.settings === "object" ? (data.settings as Record<string, unknown>) : null;
    const logFormat = settings && typeof settings.log_format === "string" ? settings.log_format : undefined;
    const logLevel = settings && typeof settings.log_level === "number" ? settings.log_level : undefined;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{message || "Config loaded"}</span>
        <span className="text-[12px] text-slate-400">
          {pkg ? `package=${pkg}` : ""}
          {entry ? `${pkg ? " · " : ""}entry=${entry}` : ""}
          {typeof fields === "number" ? `${pkg || entry ? " · " : ""}fields=${fields}` : ""}
          {logFormat ? `${pkg || entry || typeof fields === "number" ? " · " : ""}log=${logFormat}` : ""}
          {typeof logLevel === "number" ? `(${logLevel})` : ""}
        </span>
      </div>
    );
  }

  if (name === "engine.table.written") {
    const sheet = typeof data.sheet_name === "string" ? data.sheet_name : undefined;
    const range = typeof data.output_range === "string" ? data.output_range : undefined;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{message || "Table written"}</span>
        {sheet || range ? (
          <span className="text-[12px] text-slate-400">
            {sheet ? `sheet=${sheet}` : ""}
            {range ? `${sheet ? " · " : ""}range=${range}` : ""}
          </span>
        ) : null}
      </div>
    );
  }

  if (name === "engine.validation.result") {
    const validator = typeof data.validator === "string" ? data.validator : undefined;
    const field = typeof data.field === "string" ? data.field : undefined;
    const issues = typeof data.issues_found === "number" ? data.issues_found : undefined;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">
          {validator ? `Validation ${validator}` : "Validation"}
          {field ? ` · ${field}` : ""}
          {typeof issues === "number" ? ` · issues=${issues}` : ""}
        </span>
      </div>
    );
  }

  if (name === "engine.transform.result") {
    const transform = typeof data.transform === "string" ? data.transform : undefined;
    const field = typeof data.field === "string" ? data.field : undefined;
    const inLen = typeof data.input_len === "number" ? data.input_len : undefined;
    const outLen = typeof data.output_len === "number" ? data.output_len : undefined;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">
          {transform ? `Transform ${transform}` : "Transform"}
          {field ? ` · ${field}` : ""}
          {typeof inLen === "number" && typeof outLen === "number" ? ` · ${inLen}→${outLen}` : ""}
        </span>
      </div>
    );
  }

  if (name === "engine.column_detector.candidate") {
    const col = typeof data.column_index === "number" ? data.column_index : undefined;
    const header = typeof data.header === "string" ? data.header : undefined;
    const best = typeof data.best_field === "string" ? data.best_field : undefined;
    const score = typeof data.best_score === "number" ? data.best_score : undefined;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">
          Candidate
          {typeof col === "number" ? ` col=${col}` : ""}
          {header ? ` header=${JSON.stringify(header)}` : ""}
          {best ? ` · best=${best}` : ""}
          {typeof score === "number" ? ` (${score.toFixed(3)})` : ""}
        </span>
      </div>
    );
  }

  if (name === "engine.detector.column_result" || name === "engine.detector.row_result") {
    const sheet = typeof data.sheet_name === "string" ? data.sheet_name : undefined;
    const col = typeof data.column_index === "number" ? data.column_index : undefined;
    const row = typeof data.row_index === "number" ? data.row_index : undefined;
    const detector = data.detector && typeof data.detector === "object" ? (data.detector as Record<string, unknown>) : {};
    const detName = typeof detector.name === "string" ? detector.name : undefined;
    const duration = typeof detector.duration_ms === "number" ? detector.duration_ms : undefined;
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">
          Detector
          {detName ? ` ${detName}` : ""}
          {sheet ? ` · ${sheet}` : ""}
          {typeof col === "number" ? ` · col=${col}` : ""}
          {typeof row === "number" ? ` · row=${row}` : ""}
          {typeof duration === "number" ? ` · ${duration.toFixed(2)}ms` : ""}
        </span>
      </div>
    );
  }

  if (name.startsWith("build.") || name.startsWith("run.")) {
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{message || name}</span>
      </div>
    );
  }

  if (message && message !== name) {
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{message}</span>
        <span className="text-[12px] text-slate-500">{name}</span>
      </div>
    );
  }

  if (Object.keys(data).length) {
    return (
      <div className="flex flex-col gap-[2px]">
        <span className="break-words">{name}</span>
      </div>
    );
  }

  return null;
}
