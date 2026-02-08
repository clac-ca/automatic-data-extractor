import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { sessionKeys, type SessionEnvelope } from "@/api/auth/api";
import { mapUiError } from "@/api/uiErrors";
import { updateMyProfile } from "@/api/me/api";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/format";

interface ProfilePageProps {
  readonly displayName: string | null | undefined;
  readonly email: string;
  readonly createdAt?: string | null;
}

type Feedback =
  | { tone: "success"; message: string }
  | { tone: "danger"; message: string }
  | null;

export function ProfilePage({ displayName, email, createdAt }: ProfilePageProps) {
  const queryClient = useQueryClient();
  const [nameInput, setNameInput] = useState(displayName ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  useEffect(() => {
    setNameInput(displayName ?? "");
  }, [displayName]);

  const normalizedInitialName = useMemo(() => (displayName ?? "").trim(), [displayName]);
  const normalizedInput = nameInput.trim();
  const hasChanges = normalizedInitialName !== normalizedInput;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!hasChanges) {
      return;
    }

    setFeedback(null);
    setIsSaving(true);
    try {
      const profile = await updateMyProfile({
        display_name: normalizedInput.length > 0 ? normalizedInput : null,
      });

      queryClient.setQueryData<SessionEnvelope | null>(sessionKeys.detail(), (current) => {
        if (!current) {
          return current;
        }

        return {
          ...current,
          user: {
            ...current.user,
            display_name: profile.display_name,
            updated_at: profile.updated_at,
          },
        };
      });

      setFeedback({ tone: "success", message: "Profile updated. Changes now appear across ADE." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to update profile.",
        statusMessages: {
          422: "Display name is invalid. Update the value and try again.",
        },
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <section className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
        <header className="space-y-1">
          <h3 className="text-base font-semibold text-foreground">Profile details</h3>
          <p className="text-sm text-muted-foreground">
            Update your display name. This name appears in shared activity across ADE.
          </p>
        </header>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <FormField
            label="Display name"
            hint="You can leave this blank and ADE will fall back to your email identity."
          >
            <Input
              value={nameInput}
              onChange={(event) => setNameInput(event.target.value)}
              maxLength={200}
              placeholder="How should we display your name?"
              disabled={isSaving}
            />
          </FormField>

          <FormField label="Email">
            <Input value={email} readOnly aria-readonly className="text-muted-foreground" />
          </FormField>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={isSaving || !hasChanges}>
              {isSaving ? "Saving…" : "Save profile"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={isSaving || !hasChanges}
              onClick={() => setNameInput(displayName ?? "")}
            >
              Reset
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-xl border border-border bg-card p-5 shadow-xs">
        <h3 className="text-base font-semibold text-foreground">Account metadata</h3>
        <dl className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-[auto_1fr] sm:gap-x-4">
          <dt className="font-semibold text-foreground">Account email</dt>
          <dd>{email}</dd>
          <dt className="font-semibold text-foreground">Created</dt>
          <dd>{createdAt ? formatDate(createdAt) : "Unknown"}</dd>
        </dl>
      </section>
    </div>
  );
}
