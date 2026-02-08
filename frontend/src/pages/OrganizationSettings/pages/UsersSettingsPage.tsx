import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useLocation, useNavigate } from "react-router-dom";

import { buildWeakEtag } from "@/api/etag";
import { mapUiError } from "@/api/uiErrors";
import { useAuthProvidersQuery } from "@/hooks/auth/useAuthProvidersQuery";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import {
  useAdminRolesQuery,
  useAdminUserApiKeysQuery,
  useAdminUserRolesQuery,
  useAdminUsersQuery,
  useAssignAdminUserRoleMutation,
  useCreateAdminUserApiKeyMutation,
  useCreateAdminUserMutation,
  useDeactivateAdminUserMutation,
  useRemoveAdminUserRoleMutation,
  useRevokeAdminUserApiKeyMutation,
  useUpdateAdminUserMutation,
} from "@/hooks/admin";
import { useSession } from "@/providers/auth/SessionContext";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { SettingsDrawer } from "@/pages/Workspace/sections/Settings/components/SettingsDrawer";
import { SettingsSection } from "@/pages/Workspace/sections/Settings/components/SettingsSection";
import type { ApiKeySummary } from "@/types";
import { ResponsiveAdminTable } from "../components/ResponsiveAdminTable";
import { useOrganizationSettingsSection } from "../sectionContext";

type FeedbackMessage = { tone: "success" | "danger"; message: string };

type KeyReveal = {
  readonly id: string;
  readonly prefix: string;
  readonly secret: string;
};

const SIMPLE_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function UsersSettingsPage() {
  const { hasPermission } = useGlobalPermissions();
  const { params } = useOrganizationSettingsSection();
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageUsers = hasPermission("users.manage_all");
  const canReadUsers = hasPermission("users.read_all") || canManageUsers;

  const usersQuery = useAdminUsersQuery({ enabled: canReadUsers, pageSize: 100 });
  const rolesQuery = useAdminRolesQuery("global");
  const authProvidersQuery = useAuthProvidersQuery();

  const createUser = useCreateAdminUserMutation();
  const updateUser = useUpdateAdminUserMutation();
  const deactivateUser = useDeactivateAdminUserMutation();
  const assignRole = useAssignAdminUserRoleMutation();
  const removeRole = useRemoveAdminUserRoleMutation();
  const createUserApiKey = useCreateAdminUserApiKeyMutation();
  const revokeUserApiKey = useRevokeAdminUserApiKeyMutation();

  const [feedbackMessage, setFeedbackMessage] = useState<FeedbackMessage | null>(null);

  const users = usersQuery.users;
  const selectedParam = params[0];
  const isCreateOpen = selectedParam === "new";
  const selectedUserId = selectedParam && selectedParam !== "new" ? decodeURIComponent(selectedParam) : null;
  const selectedUser = users.find((entry) => entry.id === selectedUserId);

  const providers = authProvidersQuery.data?.providers ?? [];
  const ssoEnabled = providers.some((provider) => provider.type === "oidc");

  const basePath = "/organization/users";
  const suffix = `${location.search}${location.hash}`;
  const closeDrawer = () => navigate(`${basePath}${suffix}`, { replace: true });
  const openCreateDrawer = () => navigate(`${basePath}/new${suffix}`);
  const openUserDrawer = (userId: string) => navigate(`${basePath}/${encodeURIComponent(userId)}${suffix}`);

  if (!canReadUsers) {
    return (
      <Alert tone="danger">
        You do not have permission to access users.
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {feedbackMessage ? <Alert tone={feedbackMessage.tone}>{feedbackMessage.message}</Alert> : null}
      {usersQuery.isError ? (
        <Alert tone="danger">
          {mapUiError(usersQuery.error, { fallback: "Unable to load users." }).message}
        </Alert>
      ) : null}

      <SettingsSection
        title="Users"
        description={usersQuery.isLoading ? "Loading users..." : `${users.length} users`}
        actions={
          canManageUsers ? (
            <Button type="button" size="sm" onClick={openCreateDrawer} disabled={!ssoEnabled}>
              Create user
            </Button>
          ) : null
        }
      >
        {!ssoEnabled ? (
          <Alert tone="info">
            User creation is available only when SSO providers are configured.
          </Alert>
        ) : null}

        {usersQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading users...</p>
        ) : users.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-background p-4 text-sm text-muted-foreground">
            No users found.
          </p>
        ) : (
          <ResponsiveAdminTable
            items={users}
            getItemKey={(user) => user.id}
            mobileListLabel="Organization users"
            desktopTable={
              <div className="overflow-hidden rounded-xl border border-border">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      <TableHead className="px-4">User</TableHead>
                      <TableHead className="px-4">Roles</TableHead>
                      <TableHead className="px-4">Status</TableHead>
                      <TableHead className="px-4 text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
                      <TableRow key={user.id} className="text-sm text-foreground">
                        <TableCell className="px-4 py-3">
                          <p className="font-semibold text-foreground">{user.display_name || user.email}</p>
                          <p className="text-xs text-muted-foreground">{user.email}</p>
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {(user.roles ?? []).length === 0 ? (
                              <span className="text-xs text-muted-foreground">No roles</span>
                            ) : (
                              (user.roles ?? []).map((role) => (
                                <Badge key={`${user.id}-${role}`} variant="secondary" className="text-xs">
                                  {role}
                                </Badge>
                              ))
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <Badge variant={user.is_active ? "secondary" : "outline"}>
                            {user.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="px-4 py-3 text-right">
                          <Button type="button" variant="ghost" size="sm" onClick={() => openUserDrawer(user.id)}>
                            {canManageUsers ? "Manage" : "View"}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            }
            mobileCard={(user) => (
              <>
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-foreground">{user.display_name || user.email}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </div>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Roles</dt>
                  <dd>
                    {(user.roles ?? []).length === 0 ? (
                      <span className="text-muted-foreground">No roles</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {(user.roles ?? []).map((role) => (
                          <Badge key={`${user.id}-${role}`} variant="secondary" className="text-[11px]">
                            {role}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </dd>
                  <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                  <dd>
                    <Badge variant={user.is_active ? "secondary" : "outline"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </dd>
                </dl>
                <div className="flex justify-end">
                  <Button type="button" variant="ghost" size="sm" onClick={() => openUserDrawer(user.id)}>
                    {canManageUsers ? "Manage" : "View"}
                  </Button>
                </div>
              </>
            )}
          />
        )}

        {usersQuery.hasNextPage ? (
          <div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => usersQuery.fetchNextPage()}
              disabled={usersQuery.isFetchingNextPage}
            >
              {usersQuery.isFetchingNextPage ? "Loading more users..." : "Load more users"}
            </Button>
          </div>
        ) : null}

        {!canManageUsers ? (
          <Alert tone="info">You can view users, but you need user management permission to make changes.</Alert>
        ) : null}
      </SettingsSection>

      <CreateUserDrawer
        open={isCreateOpen && canManageUsers}
        canCreate={ssoEnabled}
        onClose={closeDrawer}
        onSubmit={async ({ email, displayName }) => {
          setFeedbackMessage(null);
          try {
            await createUser.mutateAsync({ email, display_name: displayName || null });
            setFeedbackMessage({ tone: "success", message: "User created." });
            closeDrawer();
          } catch (error) {
            const mapped = mapUiError(error, { fallback: "Unable to create user." });
            setFeedbackMessage({ tone: "danger", message: mapped.message });
          }
        }}
        isSubmitting={createUser.isPending}
      />

      <ManageUserDrawer
        open={Boolean(selectedUserId)}
        userId={selectedUserId}
        user={selectedUser}
        canManage={canManageUsers}
        currentUserId={session.user.id}
        roles={rolesQuery.data?.items ?? []}
        onClose={closeDrawer}
        onUpdateProfile={async (payload) => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          await updateUser.mutateAsync({ userId: selectedUserId, payload });
          setFeedbackMessage({ tone: "success", message: "User profile updated." });
        }}
        onDeactivate={async () => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          await deactivateUser.mutateAsync(selectedUserId);
          setFeedbackMessage({ tone: "success", message: "User deactivated." });
          closeDrawer();
        }}
        onSaveRoles={async (draftRoleIds, currentRoleIds) => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          const toAssign = draftRoleIds.filter((roleId) => !currentRoleIds.includes(roleId));
          const toRemove = currentRoleIds.filter((roleId) => !draftRoleIds.includes(roleId));

          await Promise.all([
            ...toAssign.map((roleId) => assignRole.mutateAsync({ userId: selectedUserId, roleId })),
            ...toRemove.map((roleId) => removeRole.mutateAsync({ userId: selectedUserId, roleId })),
          ]);
          setFeedbackMessage({ tone: "success", message: "Roles updated." });
        }}
        onCreateApiKey={async ({ name, expiresInDays }) => {
          if (!selectedUserId) return null;
          setFeedbackMessage(null);
          const created = await createUserApiKey.mutateAsync({
            userId: selectedUserId,
            payload: {
              name: name || undefined,
              expires_in_days: expiresInDays ?? undefined,
            },
          });
          setFeedbackMessage({ tone: "success", message: "API key created." });
          return created;
        }}
        onRevokeApiKey={async (key) => {
          if (!selectedUserId) return;
          setFeedbackMessage(null);
          await revokeUserApiKey.mutateAsync({
            userId: selectedUserId,
            apiKeyId: key.id,
            ifMatch: buildWeakEtag(key.id, key.revoked_at ?? key.created_at),
          });
          setFeedbackMessage({ tone: "success", message: "API key revoked." });
        }}
        isMutating={
          updateUser.isPending ||
          deactivateUser.isPending ||
          assignRole.isPending ||
          removeRole.isPending ||
          createUserApiKey.isPending ||
          revokeUserApiKey.isPending
        }
      />
    </div>
  );
}

function CreateUserDrawer({
  open,
  canCreate,
  onClose,
  onSubmit,
  isSubmitting,
}: {
  readonly open: boolean;
  readonly canCreate: boolean;
  readonly onClose: () => void;
  readonly onSubmit: (input: { email: string; displayName: string }) => Promise<void>;
  readonly isSubmitting: boolean;
}) {
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setEmail("");
      setDisplayName("");
      setError(null);
      setEmailError(null);
    }
  }, [open]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setEmailError(null);
    if (!canCreate) {
      setError("SSO must be configured before creating users.");
      return;
    }
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setEmailError("Email is required.");
      return;
    }
    if (!SIMPLE_EMAIL_PATTERN.test(trimmedEmail)) {
      setEmailError("Enter a valid email address.");
      return;
    }
    try {
      await onSubmit({ email: trimmedEmail, displayName: displayName.trim() });
    } catch (submitError) {
      const mapped = mapUiError(submitError, { fallback: "Unable to create user." });
      setError(mapped.message);
    }
  };

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title="Create user"
      description="Pre-provision an SSO user account."
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        {error ? <Alert tone="danger">{error}</Alert> : null}
        <FormField label="Email" required error={emailError}>
          <Input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="user@example.com"
            disabled={isSubmitting || !canCreate}
          />
        </FormField>
        <FormField label="Display name">
          <Input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Optional"
            disabled={isSubmitting || !canCreate}
          />
        </FormField>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting || !canCreate}>
            {isSubmitting ? "Creating..." : "Create user"}
          </Button>
        </div>
      </form>
    </SettingsDrawer>
  );
}

function ManageUserDrawer({
  open,
  userId,
  user,
  canManage,
  currentUserId,
  roles,
  onClose,
  onUpdateProfile,
  onDeactivate,
  onSaveRoles,
  onCreateApiKey,
  onRevokeApiKey,
  isMutating,
}: {
  readonly open: boolean;
  readonly userId: string | null;
  readonly user:
    | {
        id: string;
        email: string;
        display_name: string | null;
        is_active: boolean;
      }
    | undefined;
  readonly canManage: boolean;
  readonly currentUserId?: string;
  readonly roles: readonly { id: string; name: string }[];
  readonly onClose: () => void;
  readonly onUpdateProfile: (payload: { display_name?: string | null; is_active?: boolean | null }) => Promise<void>;
  readonly onDeactivate: () => Promise<void>;
  readonly onSaveRoles: (draftRoleIds: string[], currentRoleIds: string[]) => Promise<void>;
  readonly onCreateApiKey: (input: { name: string; expiresInDays: number | null }) => Promise<{ id: string; prefix: string; secret: string } | null>;
  readonly onRevokeApiKey: (key: ApiKeySummary) => Promise<void>;
  readonly isMutating: boolean;
}) {
  const userRolesQuery = useAdminUserRolesQuery(userId);
  const userApiKeysQuery = useAdminUserApiKeysQuery(userId, { includeRevoked: true, limit: 100 });
  const [displayName, setDisplayName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [roleDraft, setRoleDraft] = useState<string[]>([]);
  const [apiKeyName, setApiKeyName] = useState("");
  const [apiKeyExpiry, setApiKeyExpiry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [issuedKey, setIssuedKey] = useState<KeyReveal | null>(null);
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const hasExpiryInput = apiKeyExpiry.trim().length > 0;
  const parsedExpiry = hasExpiryInput ? Number.parseInt(apiKeyExpiry.trim(), 10) : null;
  const apiKeyExpiryError =
    hasExpiryInput && (!Number.isInteger(parsedExpiry ?? Number.NaN) || (parsedExpiry ?? 0) <= 0)
      ? "Expiration must be a positive whole number of days."
      : null;

  const currentRoleIds = useMemo(
    () => (userRolesQuery.data?.roles ?? []).map((entry) => entry.role_id),
    [userRolesQuery.data?.roles],
  );

  useEffect(() => {
    if (!open || !user) {
      setDisplayName("");
      setIsActive(true);
      setRoleDraft([]);
      setError(null);
      setIssuedKey(null);
      setCopyStatus("idle");
      return;
    }

    setDisplayName(user.display_name ?? "");
    setIsActive(Boolean(user.is_active));
  }, [open, user]);

  useEffect(() => {
    if (!open) return;
    setRoleDraft(currentRoleIds);
  }, [currentRoleIds, open]);

  const disabled = !canManage || isMutating;

  return (
    <SettingsDrawer
      open={open}
      onClose={onClose}
      title={user?.display_name || user?.email || "User"}
      description="Manage profile, global roles, and API keys."
      widthClassName="w-full max-w-2xl"
    >
      {!user ? (
        <Alert tone="warning">This user could not be found.</Alert>
      ) : (
        <div className="space-y-6">
          {error ? <Alert tone="danger">{error}</Alert> : null}
          {!canManage ? (
            <Alert tone="info">Read-only view. You need user management permission to make changes.</Alert>
          ) : null}

          {issuedKey ? (
            <div className="space-y-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3">
              <p className="text-sm font-semibold text-warning-foreground">Copy this API key secret now</p>
              <p className="text-xs text-warning-foreground/90">
                For security, this secret is shown only once and cannot be retrieved again.
              </p>
              <div className="flex flex-col gap-2 rounded-md border border-warning/40 bg-background p-3 sm:flex-row sm:items-center sm:justify-between">
                <code className="break-all text-xs text-foreground">{issuedKey.secret}</code>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(issuedKey.secret);
                        setCopyStatus("copied");
                      } catch {
                        setCopyStatus("failed");
                      }
                    }}
                  >
                    Copy
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setIssuedKey(null)}>
                    Dismiss
                  </Button>
                </div>
              </div>
              {copyStatus === "copied" ? <p className="text-xs text-success">Secret copied to clipboard.</p> : null}
              {copyStatus === "failed" ? <p className="text-xs text-destructive">Unable to copy. Copy manually.</p> : null}
            </div>
          ) : null}

          <SettingsSection title="Profile" description="Update account details and activation status.">
            <FormField label="Email">
              <Input value={user.email} disabled />
            </FormField>
            <FormField label="Display name">
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                disabled={disabled}
              />
            </FormField>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={isActive}
                onChange={(event) => setIsActive(event.target.checked)}
                disabled={disabled}
              />
              Active user
            </label>
            <div className="flex justify-end gap-2">
              {user.id !== currentUserId && user.is_active ? (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={disabled}
                  onClick={async () => {
                    setError(null);
                    try {
                      await onDeactivate();
                    } catch (deactivateError) {
                      const mapped = mapUiError(deactivateError, { fallback: "Unable to deactivate user." });
                      setError(mapped.message);
                    }
                  }}
                >
                  Deactivate
                </Button>
              ) : null}
              <Button
                type="button"
                disabled={disabled}
                onClick={async () => {
                  setError(null);
                  try {
                    await onUpdateProfile({
                      display_name: displayName.trim() || null,
                      is_active: isActive,
                    });
                  } catch (saveError) {
                    const mapped = mapUiError(saveError, { fallback: "Unable to update user." });
                    setError(mapped.message);
                  }
                }}
              >
                Save profile
              </Button>
            </div>
          </SettingsSection>

          <SettingsSection title="Global roles" description="Assign global roles to this user.">
            {roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">No global roles available.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {roles.map((role) => (
                  <label key={role.id} className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border"
                      checked={roleDraft.includes(role.id)}
                      onChange={(event) =>
                        setRoleDraft((current) =>
                          event.target.checked
                            ? Array.from(new Set([...current, role.id]))
                            : current.filter((id) => id !== role.id),
                        )
                      }
                      disabled={disabled}
                    />
                    <span>{role.name}</span>
                  </label>
                ))}
              </div>
            )}
            <div className="flex justify-end">
              <Button
                type="button"
                disabled={disabled || userRolesQuery.isLoading}
                onClick={async () => {
                  setError(null);
                  try {
                    await onSaveRoles(roleDraft, currentRoleIds);
                    await userRolesQuery.refetch();
                  } catch (saveError) {
                    const mapped = mapUiError(saveError, { fallback: "Unable to update roles." });
                    setError(mapped.message);
                  }
                }}
              >
                Save roles
              </Button>
            </div>
          </SettingsSection>

          <SettingsSection title="API keys" description="Create and revoke API keys for this user.">
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_9rem_auto] md:items-end">
              <FormField label="Name">
                <Input
                  value={apiKeyName}
                  onChange={(event) => setApiKeyName(event.target.value)}
                  placeholder="Optional"
                  disabled={disabled}
                />
              </FormField>
              <FormField label="Expires (days)" error={apiKeyExpiryError}>
                <Input
                  value={apiKeyExpiry}
                  onChange={(event) => setApiKeyExpiry(event.target.value)}
                  placeholder="Optional"
                  inputMode="numeric"
                  disabled={disabled}
                />
              </FormField>
              <Button
                type="button"
                disabled={disabled || Boolean(apiKeyExpiryError)}
                onClick={async () => {
                  setError(null);
                  if (apiKeyExpiryError) {
                    return;
                  }
                  try {
                    const created = await onCreateApiKey({
                      name: apiKeyName.trim(),
                      expiresInDays: hasExpiryInput ? parsedExpiry : null,
                    });
                    setApiKeyName("");
                    setApiKeyExpiry("");
                    setCopyStatus("idle");
                    setIssuedKey(created ? { id: created.id, prefix: created.prefix, secret: created.secret } : null);
                    await userApiKeysQuery.refetch();
                  } catch (createError) {
                    const mapped = mapUiError(createError, { fallback: "Unable to create API key." });
                    setError(mapped.message);
                  }
                }}
              >
                Create key
              </Button>
            </div>

            {userApiKeysQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading API keys...</p>
            ) : (
              <ResponsiveAdminTable
                items={userApiKeysQuery.data?.items ?? []}
                getItemKey={(key) => key.id}
                mobileListLabel="User API keys"
                desktopTable={
                  <div className="overflow-hidden rounded-xl border border-border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Prefix</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(userApiKeysQuery.data?.items ?? []).map((key) => {
                          const isRevoked = Boolean(key.revoked_at);
                          return (
                            <TableRow key={key.id}>
                              <TableCell>{key.name ?? "(unnamed)"}</TableCell>
                              <TableCell className="font-mono text-xs">{key.prefix}</TableCell>
                              <TableCell>{isRevoked ? "Revoked" : "Active"}</TableCell>
                              <TableCell className="text-right">
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="ghost"
                                  disabled={disabled || isRevoked}
                                  onClick={async () => {
                                    setError(null);
                                    try {
                                      await onRevokeApiKey(key);
                                      await userApiKeysQuery.refetch();
                                    } catch (revokeError) {
                                      const mapped = mapUiError(revokeError, {
                                        fallback: "Unable to revoke API key.",
                                        statusMessages: {
                                          412: "This key changed while you were viewing it. Refresh and retry.",
                                        },
                                      });
                                      setError(mapped.message);
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
                        <dt className="font-semibold uppercase tracking-wide text-muted-foreground">Status</dt>
                        <dd>{isRevoked ? "Revoked" : "Active"}</dd>
                      </dl>
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={disabled || isRevoked}
                          onClick={async () => {
                            setError(null);
                            try {
                              await onRevokeApiKey(key);
                              await userApiKeysQuery.refetch();
                            } catch (revokeError) {
                              const mapped = mapUiError(revokeError, {
                                fallback: "Unable to revoke API key.",
                                statusMessages: {
                                  412: "This key changed while you were viewing it. Refresh and retry.",
                                },
                              });
                              setError(mapped.message);
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
          </SettingsSection>
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <Button type="button" variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
    </SettingsDrawer>
  );
}
