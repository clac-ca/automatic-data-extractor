export type AccessActionReasonCode =
  | "perm_missing"
  | "provider_managed"
  | "dynamic_membership"
  | "invalid_selection"
  | "conflict_state";

const DEFAULT_REASON_COPY: Record<AccessActionReasonCode, string> = {
  perm_missing: "You do not have permission for this action.",
  provider_managed: "This provider-managed group is read-only in ADE.",
  dynamic_membership: "Dynamic memberships are managed by your identity provider.",
  invalid_selection: "Select a valid value to continue.",
  conflict_state: "This action is unavailable because the current state has changed.",
};

export interface AccessActionState {
  readonly disabled: boolean;
  readonly reasonCode: AccessActionReasonCode | null;
  readonly reasonText: string | null;
}

export function resolveAccessActionState(
  options: {
    readonly isDisabled?: boolean;
    readonly reasonCode?: AccessActionReasonCode | null;
    readonly reasonText?: string | null;
  } = {},
): AccessActionState {
  const isDisabled = Boolean(options.isDisabled);
  const reasonCode = options.reasonCode ?? null;
  const defaultReason = reasonCode ? DEFAULT_REASON_COPY[reasonCode] : null;
  return {
    disabled: isDisabled,
    reasonCode,
    reasonText: isDisabled ? options.reasonText ?? defaultReason : null,
  };
}
