import { useEffect, useRef } from "react";

interface HotkeyOptions {
  readonly enabled?: boolean;
  readonly allowInInputs?: boolean;
  readonly preventDefault?: boolean;
  readonly stopPropagation?: boolean;
  readonly sequenceTimeoutMs?: number;
}

export interface HotkeyConfig {
  readonly combo: string;
  readonly handler: (event: KeyboardEvent) => void;
  readonly options?: HotkeyOptions;
}

interface ChordSegment {
  readonly key: string;
  readonly ctrl?: boolean;
  readonly meta?: boolean;
  readonly alt?: boolean;
  readonly shift?: boolean;
}

interface ParsedChord {
  readonly type: "chord";
  readonly segment: ChordSegment;
}

interface ParsedSequence {
  readonly type: "sequence";
  readonly segments: readonly string[];
  readonly timeout: number;
}

type ParsedHotkey = (ParsedChord | ParsedSequence) & {
  readonly config: HotkeyConfig;
};

function normalizeKey(key: string): string {
  if (key.length === 1) {
    return key.toLowerCase();
  }
  switch (key) {
    case "ArrowUp":
      return "arrowup";
    case "ArrowDown":
      return "arrowdown";
    case "ArrowLeft":
      return "arrowleft";
    case "ArrowRight":
      return "arrowright";
    case "Escape":
      return "escape";
    case "Enter":
      return "enter";
    case " ":
    case "Space":
      return "space";
    default:
      return key.toLowerCase();
  }
}

function parseCombo(config: HotkeyConfig): ParsedHotkey | null {
  const { combo, options } = config;
  const parts = combo
    .trim()
    .split(" ")
    .map((part) => part.trim())
    .filter(Boolean);

  if (parts.length === 0) {
    return null;
  }

  if (parts.length === 1) {
    const modifiers = new Set(
      parts[0]
        .split("+")
        .map((value) => value.trim().toLowerCase())
        .filter(Boolean),
    );
    const key = normalizeKey(parts[0].split("+").pop() ?? "");
    if (!key) {
      return null;
    }
    return {
      type: "chord",
      segment: {
        key,
        ctrl: modifiers.has("ctrl") || modifiers.has("control"),
        meta: modifiers.has("meta") || modifiers.has("cmd") || modifiers.has("command"),
        alt: modifiers.has("alt") || modifiers.has("option"),
        shift: modifiers.has("shift"),
      },
      config,
    };
  }

  const segments = parts.map((part) => normalizeKey(part));
  const timeout = options?.sequenceTimeoutMs ?? 600;
  return {
    type: "sequence",
    segments,
    timeout,
    config,
  };
}

function isEditableTarget(element: HTMLElement | null): boolean {
  if (!element) {
    return false;
  }
  const tag = element.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") {
    return true;
  }
  if (element.isContentEditable) {
    return true;
  }
  return false;
}

export function useHotkeys(configs: readonly HotkeyConfig[]) {
  const configsRef = useRef(configs);
  const sequenceRef = useRef<string[]>([]);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    configsRef.current = configs;
  }, [configs]);

  useEffect(() => {
    const parsed = configsRef.current
      .map(parseCombo)
      .filter((value): value is ParsedHotkey => value !== null);

    if (parsed.length === 0) {
      return;
    }

    const resetSequence = () => {
      sequenceRef.current = [];
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      for (const { config, type } of parsed) {
        if (config.options?.enabled === false) {
          continue;
        }
        if (!config.options?.allowInInputs && isEditableTarget(event.target as HTMLElement | null)) {
          continue;
        }
        if (type === "chord") {
          if (event.repeat) {
            continue;
          }
          const { segment } = type;
          const key = normalizeKey(event.key);
          if (key !== segment.key) {
            continue;
          }
          if (Boolean(event.ctrlKey) !== Boolean(segment.ctrl)) {
            continue;
          }
          if (Boolean(event.metaKey) !== Boolean(segment.meta)) {
            continue;
          }
          if (Boolean(event.altKey) !== Boolean(segment.alt)) {
            continue;
          }
          if (Boolean(event.shiftKey) !== Boolean(segment.shift)) {
            continue;
          }
          if (config.options?.preventDefault !== false) {
            event.preventDefault();
          }
          if (config.options?.stopPropagation) {
            event.stopPropagation();
          }
          config.handler(event);
          resetSequence();
          return;
        }
      }

      const sequenceHandlers = parsed.filter((entry): entry is ParsedSequence & { config: HotkeyConfig } => entry.type === "sequence");
      if (sequenceHandlers.length === 0) {
        return;
      }

      const key = normalizeKey(event.key);

      if (event.ctrlKey || event.metaKey || event.altKey) {
        resetSequence();
        return;
      }

      sequenceRef.current = [...sequenceRef.current, key];
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }

      let matched = false;
      for (const sequence of sequenceHandlers) {
        const { config, segments, timeout } = sequence;
        if (config.options?.enabled === false) {
          continue;
        }
        const current = sequenceRef.current;
        const requiredLength = segments.length;
        if (current.length > requiredLength) {
          continue;
        }
        const isPrefix = segments.slice(0, current.length).every((segmentKey, index) => segmentKey === current[index]);
        if (!isPrefix) {
          continue;
        }
        matched = true;
        if (current.length === requiredLength) {
          if (config.options?.preventDefault !== false) {
            event.preventDefault();
          }
          if (config.options?.stopPropagation) {
            event.stopPropagation();
          }
          config.handler(event);
          resetSequence();
          return;
        }
        if (timeoutRef.current !== null) {
          window.clearTimeout(timeoutRef.current);
        }
        timeoutRef.current = window.setTimeout(() => {
          resetSequence();
        }, timeout);
      }

      if (!matched) {
        resetSequence();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      resetSequence();
    };
  }, [configs]);
}

