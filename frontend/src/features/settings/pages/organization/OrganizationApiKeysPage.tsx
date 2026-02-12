import { useState } from "react";

import { buildWeakEtag } from "@/api/etag";
import { LoadingState } from "@/components/layout";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";

import { normalizeSettingsError, useOrganizationApiKeysQuery, useRevokeOrganizationApiKeyMutation } from "../../data";
import { settingsPaths } from "../../routing/contracts";
import { SettingsAccessDenied, SettingsListLayout, SettingsErrorState, SettingsEmptyState } from "../../shared";

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export function OrganizationApiKeysPage() {
  const { permissions } = useGlobalPermissions();
  const canRead = permissions.has("api_keys.read_all") || permissions.has("api_keys.manage_all");
  const canManage = permissions.has("api_keys.manage_all");

  const [includeRevoked, setIncludeRevoked] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const query = useOrganizationApiKeysQuery(includeRevoked);
  const revokeMutation = useRevokeOrganizationApiKeyMutation();

  if (!canRead) {
    return <SettingsAccessDenied returnHref={settingsPaths.home} />;
  }

  return (
    <SettingsListLayout
      title="API keys"
      subtitle="Audit and revoke API keys issued to users in your organization."
      breadcrumbs={[
        { label: "Settings", href: settingsPaths.home },
        { label: "Organization" },
        { label: "API keys" },
      ]}
      actions={
        <label className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-sm">
          <input type="checkbox" checked={includeRevoked} onChange={(event) => setIncludeRevoked(event.target.checked)} />
          Show revoked
        </label>
      }
    >
      {errorMessage ? <Alert tone="danger">{errorMessage}</Alert> : null}
      {successMessage ? <Alert tone="success">{successMessage}</Alert> : null}

      {query.isLoading ? <LoadingState title="Loading API keys" className="min-h-[220px]" /> : null}
      {query.isError ? (
        <SettingsErrorState
          title="Unable to load API keys"
          message={normalizeSettingsError(query.error, "Unable to load API keys.").message}
        />
      ) : null}

      {query.isSuccess && query.data.items.length === 0 ? (
        <SettingsEmptyState title="No API keys" description="No API keys match your current filters." />
      ) : null}

      {query.isSuccess && query.data.items.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-border/70">
          <Table>
            <TableHeader>
              <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <TableHead className="px-4">Name</TableHead>
                <TableHead className="px-4">Prefix</TableHead>
                <TableHead className="px-4">User</TableHead>
                <TableHead className="px-4">Created</TableHead>
                <TableHead className="px-4">Status</TableHead>
                <TableHead className="px-4 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {query.data.items.map((apiKey) => (
                <TableRow key={apiKey.id}>
                  <TableCell className="px-4 py-3">{apiKey.name || "Untitled key"}</TableCell>
                  <TableCell className="px-4 py-3">{apiKey.prefix}</TableCell>
                  <TableCell className="px-4 py-3 text-muted-foreground">{apiKey.user_id}</TableCell>
                  <TableCell className="px-4 py-3 text-muted-foreground">{formatDateTime(apiKey.created_at)}</TableCell>
                  <TableCell className="px-4 py-3">
                    <Badge variant={apiKey.revoked_at ? "outline" : "secondary"}>{apiKey.revoked_at ? "Revoked" : "Active"}</Badge>
                  </TableCell>
                  <TableCell className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={!canManage || Boolean(apiKey.revoked_at) || revokeMutation.isPending}
                      onClick={async () => {
                        setErrorMessage(null);
                        setSuccessMessage(null);
                        try {
                          await revokeMutation.mutateAsync({
                            userId: apiKey.user_id,
                            apiKeyId: apiKey.id,
                            ifMatch: buildWeakEtag(apiKey.id, apiKey.revoked_at ?? apiKey.created_at),
                          });
                          setSuccessMessage("API key revoked.");
                        } catch (error) {
                          setErrorMessage(normalizeSettingsError(error, "Unable to revoke API key.").message);
                        }
                      }}
                    >
                      Revoke
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </SettingsListLayout>
  );
}
