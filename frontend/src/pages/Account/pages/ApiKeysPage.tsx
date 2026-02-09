import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { createMyApiKey, listMyApiKeys, revokeMyApiKey } from "@/api/api-keys/api";
import { mapUiError } from "@/api/uiErrors";
import type { ApiKeySummary } from "@/types";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { formatDate } from "@/lib/format";

type Feedback =
  | { tone: "success"; message: string }
  | { tone: "danger"; message: string }
  | null;

const EXPIRY_OPTIONS: Array<{ label: string; value: string; days: number | null }> = [
  { label: "90 days (recommended)", value: "90", days: 90 },
  { label: "30 days", value: "30", days: 30 },
  { label: "180 days", value: "180", days: 180 },
  { label: "Never expires", value: "never", days: null },
];

export function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeySummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const [expiryValue, setExpiryValue] = useState(EXPIRY_OPTIONS[0].value);
  const [revealSecret, setRevealSecret] = useState<string | null>(null);
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false);
  const [selectedForRevoke, setSelectedForRevoke] = useState<ApiKeySummary | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const loadKeys = useCallback(async (mode: "initial" | "refresh" = "refresh") => {
    if (mode === "initial") {
      setIsLoading(true);
    } else {
      setIsRefreshing(true);
    }

    try {
      const page = await listMyApiKeys({ includeRevoked: true, includeTotal: true, limit: 100 });
      setKeys(page.items ?? []);
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to load API keys.",
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      if (mode === "initial") {
        setIsLoading(false);
      } else {
        setIsRefreshing(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadKeys("initial");
  }, [loadKeys]);

  const sortedKeys = useMemo(
    () =>
      [...keys].sort((left, right) => {
        const leftDate = left.created_at ? Date.parse(left.created_at) : 0;
        const rightDate = right.created_at ? Date.parse(right.created_at) : 0;
        return rightDate - leftDate;
      }),
    [keys],
  );

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback(null);
    setRevealSecret(null);
    setIsCreating(true);

    try {
      const selectedExpiry = EXPIRY_OPTIONS.find((option) => option.value === expiryValue) ?? EXPIRY_OPTIONS[0];
      const result = await createMyApiKey({
        name: nameInput.trim().length > 0 ? nameInput.trim() : undefined,
        expires_in_days: selectedExpiry.days ?? undefined,
      });
      setRevealSecret(result.secret);
      setNameInput("");
      setExpiryValue(EXPIRY_OPTIONS[0].value);
      await loadKeys();
      setFeedback({ tone: "success", message: "API key created. Copy it now because it will not be shown again." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to create API key.",
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopySecret = async () => {
    if (!revealSecret) {
      return;
    }

    try {
      await navigator.clipboard.writeText(revealSecret);
      setFeedback({ tone: "success", message: "API key copied to clipboard." });
    } catch {
      setFeedback({ tone: "danger", message: "Clipboard access failed. Select and copy the key manually." });
    }
  };

  const openRevokeDialog = (apiKey: ApiKeySummary) => {
    setSelectedForRevoke(apiKey);
    setRevokeDialogOpen(true);
  };

  const handleRevoke = async () => {
    if (!selectedForRevoke) {
      return;
    }

    setIsRevoking(true);
    setFeedback(null);

    try {
      await revokeMyApiKey(selectedForRevoke.id, { ifMatch: "*" });
      setRevokeDialogOpen(false);
      setSelectedForRevoke(null);
      await loadKeys();
      setFeedback({ tone: "success", message: "API key revoked." });
    } catch (error) {
      const mapped = mapUiError(error, {
        fallback: "Unable to revoke API key.",
      });
      setFeedback({ tone: "danger", message: mapped.message });
    } finally {
      setIsRevoking(false);
    }
  };

  return (
    <div className="space-y-5">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}

      <section className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
        <header className="space-y-1">
          <h3 className="text-base font-semibold text-foreground">Create API key</h3>
          <p className="text-sm text-muted-foreground">
            API keys are global user credentials. They inherit the same workspace and route access that your user has.
          </p>
        </header>

        <form className="grid gap-3 md:grid-cols-[minmax(0,1fr)_16rem_auto]" onSubmit={handleCreate}>
          <FormField label="Key name" hint="Optional label to track key purpose.">
            <Input
              value={nameInput}
              onChange={(event) => setNameInput(event.target.value)}
              placeholder="CI deployment key"
              maxLength={100}
              disabled={isCreating}
            />
          </FormField>
          <FormField label="Expiration">
            <select
              className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground"
              value={expiryValue}
              onChange={(event) => setExpiryValue(event.target.value)}
              disabled={isCreating}
            >
              {EXPIRY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </FormField>
          <div className="flex items-end">
            <Button type="submit" disabled={isCreating} className="w-full md:w-auto">
              {isCreating ? "Creating…" : "Create key"}
            </Button>
          </div>
        </form>

        {revealSecret ? (
          <div className="space-y-3 rounded-lg border border-warning/30 bg-warning/10 p-4">
            <p className="text-sm font-semibold text-foreground">Copy this key now</p>
            <Input value={revealSecret} readOnly className="font-mono text-xs" />
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={handleCopySecret}>
                Copy key
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setRevealSecret(null)}>
                Hide key
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">For security, this secret is shown only once.</p>
          </div>
        ) : null}
      </section>

      <section className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold text-foreground">Your API keys</h3>
          <Button type="button" variant="ghost" size="sm" onClick={() => void loadKeys()} disabled={isRefreshing}>
            {isRefreshing ? "Refreshing…" : "Refresh"}
          </Button>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading API keys…</p>
        ) : sortedKeys.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No API keys created yet.
          </p>
        ) : (
          <>
            <div className="hidden overflow-hidden rounded-xl border border-border md:block">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">Name</th>
                    <th className="px-3 py-2">Prefix</th>
                    <th className="px-3 py-2">Created</th>
                    <th className="px-3 py-2">Last used</th>
                    <th className="px-3 py-2">Expires</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedKeys.map((key) => {
                    const isRevoked = Boolean(key.revoked_at);
                    return (
                      <tr key={key.id} className="border-t border-border/70 align-top text-foreground">
                        <td className="px-3 py-3">{key.name ?? "(unnamed)"}</td>
                        <td className="px-3 py-3 font-mono text-xs text-muted-foreground">{key.prefix}</td>
                        <td className="px-3 py-3 text-muted-foreground">{formatDate(key.created_at)}</td>
                        <td className="px-3 py-3 text-muted-foreground">
                          {key.last_used_at ? formatDate(key.last_used_at, { month: "short" }) : "Never"}
                        </td>
                        <td className="px-3 py-3 text-muted-foreground">
                          {key.expires_at ? formatDate(key.expires_at, { month: "short" }) : "Never"}
                        </td>
                        <td className="px-3 py-3">
                          <Badge variant={isRevoked ? "outline" : "secondary"}>
                            {isRevoked ? "Revoked" : "Active"}
                          </Badge>
                        </td>
                        <td className="px-3 py-3 text-right">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={isRevoked}
                            onClick={() => openRevokeDialog(key)}
                          >
                            Revoke
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <ul className="grid gap-3 md:hidden">
              {sortedKeys.map((key) => {
                const isRevoked = Boolean(key.revoked_at);
                return (
                  <li key={key.id} className="space-y-3 rounded-lg border border-border bg-background p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-foreground">{key.name ?? "(unnamed)"}</p>
                      <Badge variant={isRevoked ? "outline" : "secondary"}>{isRevoked ? "Revoked" : "Active"}</Badge>
                    </div>
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      <dt className="font-semibold text-foreground">Prefix</dt>
                      <dd className="font-mono">{key.prefix}</dd>
                      <dt className="font-semibold text-foreground">Created</dt>
                      <dd>{formatDate(key.created_at)}</dd>
                      <dt className="font-semibold text-foreground">Expires</dt>
                      <dd>{key.expires_at ? formatDate(key.expires_at, { month: "short" }) : "Never"}</dd>
                    </dl>
                    <div className="flex justify-end">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={isRevoked}
                        onClick={() => openRevokeDialog(key)}
                      >
                        Revoke
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </section>

      <ConfirmDialog
        open={revokeDialogOpen}
        title="Revoke API key?"
        description="This action is immediate and cannot be undone. Any clients using this key will stop working."
        confirmLabel={isRevoking ? "Revoking…" : "Revoke key"}
        cancelLabel="Cancel"
        tone="danger"
        isConfirming={isRevoking}
        onCancel={() => {
          if (isRevoking) {
            return;
          }
          setRevokeDialogOpen(false);
          setSelectedForRevoke(null);
        }}
        onConfirm={() => {
          void handleRevoke();
        }}
      />
    </div>
  );
}
