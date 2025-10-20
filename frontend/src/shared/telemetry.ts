type TelemetryPayload = Record<string, unknown>;

export interface TelemetryEvent {
  readonly name: string;
  readonly payload?: TelemetryPayload;
}

// Placeholder implementation until telemetry pipeline is wired.
export function trackEvent(event: TelemetryEvent) {
  if (import.meta.env.PROD) {
    // TODO: send event to backend once endpoint is available.
    return;
  }
  console.info(`[telemetry] ${event.name}`, event.payload ?? {});
}
