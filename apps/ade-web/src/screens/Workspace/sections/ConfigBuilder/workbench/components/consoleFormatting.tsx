import type { WorkbenchConsoleLine } from "../types";

export function resolveSeverity(level: WorkbenchConsoleLine["level"] | "all"): number {
  if (level === "error") return 3;
  if (level === "warning") return 2;
  if (level === "success") return 1;
  if (level === "info") return 1;
  return 0;
}

export function renderConsoleMessage(message: string) {
  const parsed = safeParseJson(message);
  if (!parsed) {
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
    return message;
  }
  const known = formatStructuredEvent(parsed);
  if (known) {
    return known;
  }
  const pretty = JSON.stringify(parsed, null, 2);
  return (
    <pre className="whitespace-pre-wrap break-words text-[13px] leading-relaxed text-[#d4d4d4]">
      {highlightJson(pretty)}
    </pre>
  );
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

function highlightJson(text: string) {
  const regex =
    /("(?:\\.|[^"])*"(?=:)|"(?:\\.|[^"])*")|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|\b(true|false|null)\b/g;
  const parts: Array<string | JSX.Element> = [];
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

function formatStructuredEvent(event: Record<string, unknown>) {
  const type = typeof event.type === "string" ? event.type : "";
  const payload = (event.payload ?? {}) as Record<string, unknown>;
  const status = typeof payload.status === "string" ? payload.status : undefined;
  const reason = typeof payload.reason === "string" ? payload.reason : undefined;
  const step = typeof payload.step === "string" ? payload.step : undefined;
  const message = typeof payload.message === "string" ? payload.message : undefined;
  const durationMs =
    typeof payload.duration_ms === "number" && Number.isFinite(payload.duration_ms)
      ? payload.duration_ms
      : undefined;

  const formatDuration = (valueMs: number | undefined) => {
    if (!valueMs || valueMs < 0) return "";
    if (valueMs < 1000) return `${Math.round(valueMs)} ms`;
    if (valueMs < 60_000) return `${(valueMs / 1000).toFixed(1)} s`;
    const minutes = Math.floor(valueMs / 60_000);
    const seconds = Math.round((valueMs % 60_000) / 1000);
    return `${minutes}m ${seconds}s`;
  };

  switch (type) {
    case "run.queued": {
      const mode = typeof payload.mode === "string" ? payload.mode : undefined;
      return `Run queued${mode ? ` (${mode})` : ""}.`;
    }
    case "run.waiting_for_build":
      return `Waiting for build${reason ? ` (${reason})` : ""}${payload.build_id ? ` · ${payload.build_id}` : ""}`;
    case "run.start":
    case "run.started":
    case "engine.start": {
      const mode = typeof payload.mode === "string" ? payload.mode : undefined;
      return `Run started${mode ? ` (${mode})` : ""}.`;
    }
    case "run.complete":
    case "run.completed":
    case "engine.run.summary":
    case "engine.complete":
      return `Run ${status ?? "completed"}${durationMs ? ` in ${formatDuration(durationMs)}` : ""}.`;
    case "build.queued":
      return `Build queued${reason ? ` (${reason})` : ""}.`;
    case "build.start":
    case "build.started":
      return `Build started${reason ? ` (${reason})` : ""}.`;
    case "build.complete":
    case "build.completed":
      return `Build ${status ?? "completed"}.`;
    case "build.phase.start":
    case "build.phase.started":
      return `Starting ${typeof payload.phase === "string" ? payload.phase : "build"}${message ? ` · ${message}` : ""}`;
    case "build.phase.complete":
    case "build.phase.completed": {
      const phase = typeof payload.phase === "string" ? payload.phase : "build";
      return `${phase} ${status ?? "completed"}${durationMs ? ` in ${formatDuration(durationMs)}` : ""}.`;
    }
    case "build.progress":
      return message ?? (step ? `Build: ${step}` : "Build progress");
    default:
      if (type.startsWith("run.phase.") || type.startsWith("engine.phase.")) {
        const phase = typeof payload.phase === "string" ? payload.phase : "phase";
        if (type.endsWith(".completed") || type.endsWith(".complete")) {
          return `${phase} ${status ?? "completed"}${durationMs ? ` in ${formatDuration(durationMs)}` : ""}.`;
        }
        if (type.endsWith(".started") || type.endsWith(".start")) {
          return `Starting ${phase}${message ? ` · ${message}` : ""}`;
        }
      }
      if (type.startsWith("build.phase.")) {
        const phase = typeof payload.phase === "string" ? payload.phase : "build";
        if (type.endsWith(".completed") || type.endsWith(".complete")) {
          return `${phase} ${status ?? "completed"}${durationMs ? ` in ${formatDuration(durationMs)}` : ""}.`;
        }
        if (type.endsWith(".started") || type.endsWith(".start")) {
          return `Starting ${phase}${message ? ` · ${message}` : ""}`;
        }
      }
      return null;
  }
}
