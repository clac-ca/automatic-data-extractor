import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, Signal, computed, inject, signal } from '@angular/core';
import { take } from 'rxjs/operators';

import { DEFAULT_WORKSPACE_ID } from '../constants';

export interface WorkspaceSummary {
  id: string;
  name: string;
}

type DirectoryStatus = 'idle' | 'loading' | 'loaded' | 'error';

interface WorkspaceDirectoryState {
  status: DirectoryStatus;
  workspaces: WorkspaceSummary[];
  error: string | null;
}

const INITIAL_STATE: WorkspaceDirectoryState = {
  status: 'idle',
  workspaces: [],
  error: null,
};

@Injectable({ providedIn: 'root' })
export class WorkspaceDirectoryService {
  private static readonly DIRECTORY_ENDPOINT = '/api/v1/workspaces';

  private readonly http = inject(HttpClient);

  private readonly state = signal<WorkspaceDirectoryState>(INITIAL_STATE);

  readonly status: Signal<DirectoryStatus> = computed(() => this.state().status);

  readonly loading = computed(() => this.status() === 'loading');

  readonly workspaces = computed(() => this.state().workspaces);

  readonly hasWorkspaces = computed(() => this.workspaces().length > 0);

  readonly error = computed(() => this.state().error);

  readonly defaultWorkspaceId = computed(
    () => this.workspaces()[0]?.id ?? DEFAULT_WORKSPACE_ID,
  );

  initialise(): void {
    if (this.status() === 'idle') {
      this.reload();
    }
  }

  reload(): void {
    this.state.update((state) => ({ ...state, status: 'loading', error: null }));

    this.http
      .get<WorkspaceSummary[]>(WorkspaceDirectoryService.DIRECTORY_ENDPOINT)
      .pipe(take(1))
      .subscribe({
        next: (workspaces) => {
          this.state.set({
            status: 'loaded',
            workspaces,
            error: null,
          });
        },
        error: (error: HttpErrorResponse) => {
          this.state.update((state) => ({
            ...state,
            status: 'error',
            error: this.describeError(error),
          }));
        },
      });
  }

  private describeError(error: HttpErrorResponse): string {
    if (error.status === 0) {
      return 'Unable to reach the server. Check your connection and retry.';
    }

    if (typeof error.error === 'object' && error.error?.detail) {
      return String(error.error.detail);
    }

    return `Failed to load workspaces (status ${error.status || 'unknown'}).`;
  }
}
