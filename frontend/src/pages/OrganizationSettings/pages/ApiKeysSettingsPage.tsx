import { useState } from "react";

import { buildWeakEtag } from "@/api/etag";
import { mapUiError } from "@/api/uiErrors";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import { useRevokeAdminUserApiKeyMutation, useTenantApiKeysQuery } from "@/hooks/admin";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function isValidUuidFilter(value: string): boolean {
  return UUID_PATTERN.test(value.trim());
}

export function ApiKeysSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const canManage = hasPermission("api_keys.manage_all");
  const canRead = hasPermission("api_keys.read_all") || canManage;

  const [search, setSearch] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [feedback, setFeedback] = useState<{ tone: "success" | "danger"; message: string } | null>(null);
  const trimmedUserId = userIdFilter.trim();
  const hasUserIdFilter = trimmedUserId.length > 0;
  const userIdError =
    hasUserIdFilter && !isValidUuidFilter(trimmedUserId)
      ? "Enter a valid user ID in UUID format."
      : null;

  const keysQuery = useTenantApiKeysQuery({
    enabled: canRead && !userIdError,
    pageSize: 100,
    search,
    includeRevoked,
    userId: hasUserIdFilter ? trimmedUserId : null,
  });

  const revokeMutation = useRevokeAdminUserApiKeyMutation();

  if (!canRead) {
    return <Alert tone="danger">You do not have permission to access API keys.</Alert>;
  }

  return (
    <div className="space-y-6">
      {feedback ? <Alert tone={feedback.tone}>{feedback.message}</Alert> : null}
      {keysQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(keysQuery.error, {
            fallback: "Unable to load API keys.",
            statusMessages: { 422: "One or more filters are invalid. Review your filter values and retry." },
          }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="API keys"
        description={keysQuery.isLoading ? "Loading keys…" : `${keysQuery.total} key${keysQuery.total === 1 ? "" : "s"}`}
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <FormField label="Search">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by key name or prefix"
            />
          </FormField>
          <FormField label="Filter by user ID" error={userIdError}>
            <Input
              value={userIdFilter}
              onChange={(event) => setUserIdFilter(event.target.value)}
              placeholder="Optional user ID"
            />
          </FormField>
          <label className="mt-7 flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-border"
              checked={includeRevoked}
              onChange={(event) => setIncludeRevoked(event.target.checked)}
            />
            Include revoked
          </label>
        </div>

        {keysQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading API keys…</p>
        ) : userIdError ? (
          <Alert tone="warning">Provide a valid user ID to run this filter.</Alert>
        ) : keysQuery.apiKeys.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            {search.trim() || hasUserIdFilter || includeRevoked
              ? "No API keys match your current filters."
              : "No API keys have been created for this organization yet."}
          </p>
        ) : (
          <ResponsiveAdminTable
            items={keysQuery.apiKeys}
            getItemKey={(key) => key.id}
            mobileListLabel="Organization API keys"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">Name</TableHead>
                      <TableHead className="px-4">User ID</TableHead>
                      <TableHead className="px-4">Prefix</TableHead>
                      <TableHead className="px-4">Status</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {keysQuery.apiKeys.map((key) => {
                      const isRevoked = Boolean(key.revoked_at);
                      return (
                        <TableRow key={key.id} className="text-sm text-foreground">
                          <TableCell className="px-4 py-3">{key.name ?? "(unnamed)"}</TableCell>
                          <TableCell className="px-4 py-3 font-mono text-xs text-muted-foreground">{key.user_id}</TableCell>
                          <TableCell className="px-4 py-3 font-mono text-xs text-muted-foreground">{key.prefix}</TableCell>
                          <TableCell className="px-4 py-3">
                            <Badge variant={isRevoked ? "outline" : "secondary"}>
                              {isRevoked ? "Revoked" : "Active"}
                            </Badge>
                          </TableCell>
                          <TableCell className="px-4 py-3 text-right">
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              disabled={!canManage || isRevoked || revokeMutation.isPending}
                              onClick={async () => {
                                setFeedback(null);
                                try {
                                  await revokeMutation.mutateAsync({
                                    userId: key.user_id,
                                    apiKeyId: key.id,
                                    ifMatch: buildWeakEtag(key.id, key.revoked_at ?? key.created_at),
                                  });
                                  setFeedback({ tone: "success", message: "API key revoked." });
                                } catch (error) {
                                  const mapped = mapUiError(error, {
                                    fallback: "Unable to revoke API key.",
                                  });
                                  setFeedback({ tone: "danger", message: mapped.message });
                                }
                              }}
                            >
                              Revoke
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(key) => {
              const isRevoked = Boolean(key.revoked_at);
              return (
                <>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-foreground">{key.name ?? "(unnamed)"}</p>
                    <p className="font-mono text-[11px] text-muted-foreground">{key.prefix}</p>
                  </div>
                  <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                    <dt className="font-semibold uppercase tracking-wide text-muted-foreground">User</dt>
                    <dd className="font-mono text-muted-foreground">{key.user_id}</dd>
                    <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                    <dd>
                      <Badge variant={isRevoked ? "outline" : "secondary"}>
                        {isRevoked ? "Revoked" : "Active"}
                      </Badge>
                    </dd>
                  </dl>
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={!canManage || isRevoked || revokeMutation.isPending}
                      onClick={async () => {
                        setFeedback(null);
                        try {
                          await revokeMutation.mutateAsync({
                            userId: key.user_id,
                            apiKeyId: key.id,
                            ifMatch: buildWeakEtag(key.id, key.revoked_at ?? key.created_at),
                          });
                          setFeedback({ tone: "success", message: "API key revoked." });
                        } catch (error) {
                          const mapped = mapUiError(error, {
                            fallback: "Unable to revoke API key.",
                          });
                          setFeedback({ tone: "danger", message: mapped.message });
                        }
                      }}
                    >
                      Revoke
                    </Button>
                  </div>
                </>
              );
            }}
          />
        )}

        {!canManage ? (
          <Alert tone="info">You can audit API keys, but you need API key management permission to revoke keys.</Alert>
        ) : null}

        {keysQuery.hasNextPage ? (
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => keysQuery.fetchNextPage()}
              disabled={keysQuery.isFetchingNextPage}
            >
              {keysQuery.isFetchingNextPage ? "Loading more keys…" : "Load more keys"}
            </Button>
          </div>
        ) : null}
      </SettingsSection>
    </div>
  );
}
