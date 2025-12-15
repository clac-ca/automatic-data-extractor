import type { WorkbenchConsoleLine } from "../types";

type Listener = () => void;

export type ConsoleSnapshot = {
  readonly version: number;
  readonly length: number;
  readonly capacity: number;
};

class RingBuffer<T> {
  private readonly buffer: Array<T | undefined>;
  private start = 0;
  private _length = 0;

  constructor(private readonly capacity: number) {
    if (!Number.isFinite(capacity) || capacity <= 0) {
      throw new Error("RingBuffer capacity must be a positive number.");
    }
    this.buffer = new Array<T | undefined>(capacity);
  }

  get length() {
    return this._length;
  }

  clear() {
    this.buffer.fill(undefined);
    this.start = 0;
    this._length = 0;
  }

  push(value: T) {
    if (this._length < this.capacity) {
      const index = (this.start + this._length) % this.capacity;
      this.buffer[index] = value;
      this._length += 1;
      return;
    }
    this.buffer[this.start] = value;
    this.start = (this.start + 1) % this.capacity;
  }

  get(index: number): T | undefined {
    if (index < 0 || index >= this._length) return undefined;
    const internalIndex = (this.start + index) % this.capacity;
    return this.buffer[internalIndex];
  }

  toArray(): T[] {
    const out: T[] = [];
    for (let i = 0; i < this._length; i += 1) {
      const value = this.get(i);
      if (value !== undefined) out.push(value);
    }
    return out;
  }
}

export class WorkbenchConsoleStore {
  private readonly listeners = new Set<Listener>();
  private readonly buffer: RingBuffer<WorkbenchConsoleLine>;
  private version = 0;
  private snapshot: ConsoleSnapshot;
  private notifyScheduled = false;
  private nextId = 1;

  constructor(
    private readonly capacity: number,
    initialLines?: readonly WorkbenchConsoleLine[],
  ) {
    this.buffer = new RingBuffer<WorkbenchConsoleLine>(capacity);
    this.snapshot = {
      version: this.version,
      length: this.buffer.length,
      capacity: this.capacity,
    };
    if (initialLines?.length) {
      this.appendMany(initialLines);
    }
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getSnapshot = (): ConsoleSnapshot => this.snapshot;

  get length() {
    return this.buffer.length;
  }

  getLine(index: number): WorkbenchConsoleLine | undefined {
    return this.buffer.get(index);
  }

  toArray(): WorkbenchConsoleLine[] {
    return this.buffer.toArray();
  }

  clear() {
    this.buffer.clear();
    this.bump();
  }

  append(line: WorkbenchConsoleLine) {
    this.buffer.push(ensureLineId(line, this.nextId++));
    this.scheduleNotify();
  }

  appendMany(lines: readonly WorkbenchConsoleLine[]) {
    for (const line of lines) {
      this.buffer.push(ensureLineId(line, this.nextId++));
    }
    this.scheduleNotify();
  }

  private bump() {
    this.version += 1;
    this.snapshot = {
      version: this.version,
      length: this.buffer.length,
      capacity: this.capacity,
    };
    for (const listener of this.listeners) listener();
  }

  private scheduleNotify() {
    if (this.notifyScheduled) return;
    this.notifyScheduled = true;

    const flush = () => {
      this.notifyScheduled = false;
      this.bump();
    };

    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(flush);
      return;
    }
    setTimeout(flush, 0);
  }
}

function ensureLineId(line: WorkbenchConsoleLine, fallbackId: number): WorkbenchConsoleLine {
  if (line.id) return line;
  const origin = line.origin ?? "run";
  const timestamp = line.timestamp ?? "ts";
  return { ...line, id: `console-${origin}-${timestamp}-${fallbackId}` };
}
