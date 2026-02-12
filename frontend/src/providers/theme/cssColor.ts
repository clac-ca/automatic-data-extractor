export function resolveCssColor(variable: string, fallback: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return fallback;
  }
  const resolved = resolveCssVarColor(variable, fallback);
  const rgb = parseRgbColor(resolved);
  if (!rgb) {
    return fallback;
  }
  return rgbToHex(rgb[0], rgb[1], rgb[2]);
}

export function resolveCssRgbaColor(variable: string, fallback: string): string {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return fallback;
  }
  const resolved = resolveCssVarColor(variable, fallback);
  const rgba = parseRgbaColor(resolved);
  if (!rgba) {
    return fallback;
  }
  return toRgbaString(rgba[0], rgba[1], rgba[2], rgba[3]);
}

export function resolveCssVarColor(variable: string, fallback: string): string {
  const root = document.documentElement;
  if (!root) {
    return fallback;
  }
  const probe = document.createElement("span");
  probe.style.color = `var(${variable}, ${fallback})`;
  probe.style.position = "absolute";
  probe.style.opacity = "0";
  probe.style.pointerEvents = "none";
  probe.style.userSelect = "none";
  root.appendChild(probe);
  try {
    const computed = getComputedStyle(probe).color.trim();
    return computed || fallback;
  } finally {
    root.removeChild(probe);
  }
}

export function parseRgbColor(value: string): [number, number, number] | null {
  const rgba = parseRgbaColor(value);
  if (!rgba) {
    return null;
  }
  return [rgba[0], rgba[1], rgba[2]];
}

export function rgbToHex(red: number, green: number, blue: number): string {
  const toHex = (value: number) => {
    const clamped = Math.max(0, Math.min(255, Math.round(value)));
    return clamped.toString(16).padStart(2, "0");
  };
  return `#${toHex(red)}${toHex(green)}${toHex(blue)}`;
}

let colorContext: CanvasRenderingContext2D | null = null;

export function parseRgbaColor(value: string): [number, number, number, number] | null {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return null;
  }
  const context = getColorContext();
  if (!context) {
    return null;
  }

  // Detect invalid colors by observing unchanged fillStyle after assignment.
  context.fillStyle = "rgba(1, 2, 3, 1)";
  const before = context.fillStyle;
  try {
    context.fillStyle = value;
  } catch {
    return null;
  }
  const after = context.fillStyle;
  if (after === before && normalizeColor(value) !== normalizeColor(before)) {
    return null;
  }

  context.clearRect(0, 0, 1, 1);
  context.fillRect(0, 0, 1, 1);
  const [red, green, blue, alpha] = context.getImageData(0, 0, 1, 1).data;
  return [red, green, blue, alpha / 255];
}

function getColorContext(): CanvasRenderingContext2D | null {
  if (colorContext) {
    return colorContext;
  }
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    return null;
  }
  colorContext = context;
  return colorContext;
}

function normalizeColor(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "");
}

function toRgbaString(red: number, green: number, blue: number, alpha: number): string {
  const formattedAlpha = Number(alpha.toFixed(4));
  if (formattedAlpha >= 1) {
    return `rgb(${red}, ${green}, ${blue})`;
  }
  return `rgba(${red}, ${green}, ${blue}, ${formattedAlpha})`;
}
