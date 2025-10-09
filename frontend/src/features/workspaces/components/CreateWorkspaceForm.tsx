import { type FormEvent, useState } from "react";

import { ApiError } from "../../../shared/api/client";
import type { WorkspaceProfile } from "../../../shared/api/types";
import { useCreateWorkspaceMutation } from "../hooks/useCreateWorkspaceMutation";

interface CreateWorkspaceFormProps {
  onCreated: (workspace: WorkspaceProfile) => void;
  onCancel?: () => void;
  autoFocus?: boolean;
}

export function CreateWorkspaceForm({ onCreated, onCancel, autoFocus = false }: CreateWorkspaceFormProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { mutateAsync, isPending } = useCreateWorkspaceMutation();

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Enter a workspace name.");
      return;
    }

    setError(null);

    try {
      const created = await mutateAsync({ name: trimmedName });

      setName("");
      onCreated(created);
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError(cause.problem?.detail ?? cause.message);
        return;
      }

      setError("We couldn't create the workspace. Try again.");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div>
        <label htmlFor="workspace-name" className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
          Workspace name
        </label>
        <input
          id="workspace-name"
          name="workspace-name"
          type="text"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
            if (error) {
              setError(null);
            }
          }}
          disabled={isPending}
          autoFocus={autoFocus}
          data-autofocus={autoFocus ? "true" : undefined}
          className="mt-2 w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-100 shadow-inner focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
          placeholder="e.g. Finance Operations"
        />
      </div>
      <p className="text-xs text-slate-500">
        You'll be the workspace owner. Add teammates later from the workspace settings.
      </p>
      {error && (
        <p className="text-sm text-rose-300" role="alert">
          {error}
        </p>
      )}
      <div className="flex items-center justify-end gap-3">
        {onCancel && (
          <button
            type="button"
            onClick={() => {
              setName("");
              setError(null);
              onCancel();
            }}
            disabled={isPending}
            className="rounded border border-slate-700 px-3 py-2 text-sm font-medium text-slate-300 hover:border-slate-500 hover:text-slate-100 disabled:cursor-not-allowed disabled:border-slate-900 disabled:text-slate-500"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={isPending}
          className="inline-flex items-center rounded bg-sky-500 px-3 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:bg-sky-800 disabled:text-slate-400"
        >
          {isPending ? "Creating…" : "Create workspace"}
        </button>
      </div>
    </form>
  );
}
