import { Alert, type AlertTone } from "@/components/ui/alert";

export interface SettingsFeedbackMessage {
  readonly id?: string;
  readonly tone: AlertTone;
  readonly heading?: string;
  readonly message: string;
}

export function SettingsFeedbackRegion({
  messages,
}: {
  readonly messages: readonly SettingsFeedbackMessage[];
}) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2" aria-live="polite" aria-atomic="true">
      {messages.map((entry, index) => (
        <Alert
          key={entry.id ?? `${entry.tone}-${index}`}
          tone={entry.tone}
          heading={entry.heading}
          aria-live={entry.tone === "danger" ? "assertive" : "polite"}
        >
          {entry.message}
        </Alert>
      ))}
    </div>
  );
}
