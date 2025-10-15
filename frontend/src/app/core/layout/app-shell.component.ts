import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { NgClass } from '@angular/common';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { DEFAULT_WORKSPACE_ID } from '../constants';
import { WorkspaceDirectoryService, WorkspaceSummary } from '../workspaces/workspace-directory.service';

interface WorkspaceNavLink {
  label: string;
  path: string;
}

@Component({
  selector: 'app-app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, NgClass],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppShellComponent implements OnInit {
  private static readonly WORKSPACE_ROUTE_PATTERN = /^\/workspaces\/([^/]+)/;

  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private readonly workspaceDirectory = inject(WorkspaceDirectoryService);

  protected readonly sidebarOpen = signal(true);
  private readonly currentUrl = signal(this.router.url);

  protected readonly workspaces = this.workspaceDirectory.workspaces;
  protected readonly loadingWorkspaces = this.workspaceDirectory.loading;
  protected readonly workspaceError = this.workspaceDirectory.error;
  protected readonly hasWorkspaces = this.workspaceDirectory.hasWorkspaces;

  protected readonly currentWorkspaceId = computed(() => {
    const match = AppShellComponent.WORKSPACE_ROUTE_PATTERN.exec(
      this.currentUrl(),
    );
    return match ? decodeURIComponent(match[1]) : null;
  });

  protected readonly activeWorkspaceId = computed(() =>
    this.currentWorkspaceId() ?? this.workspaceDirectory.defaultWorkspaceId(),
  );

  protected readonly activeWorkspace = computed(() =>
    this.findWorkspace(this.activeWorkspaceId()),
  );

  protected readonly workspaceNavVisible = computed(
    () => this.currentWorkspaceId() !== null && this.hasWorkspaces(),
  );

  protected readonly workspaceNavLinks: WorkspaceNavLink[] = [
    { label: 'Documents', path: 'documents' },
    { label: 'Configurations', path: 'configurations' },
    { label: 'Jobs', path: 'jobs' },
  ];

  protected readonly workspaceDocumentsLink = computed(() =>
    this.workspaceLink('documents'),
  );

  constructor() {
    const subscription = this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => this.currentUrl.set(event.urlAfterRedirects));

    this.destroyRef.onDestroy(() => subscription.unsubscribe());

    effect(() => {
      if (!this.workspaceNavVisible() && !this.sidebarOpen()) {
        this.sidebarOpen.set(true);
      }
    });
  }

  ngOnInit(): void {
    this.workspaceDirectory.initialise();
  }

  toggleSidebar(): void {
    if (!this.workspaceNavVisible()) {
      return;
    }
    this.sidebarOpen.update((value) => !value);
  }

  protected onWorkspaceSelect(workspaceId: string): void {
    const target =
      workspaceId || this.workspaceDirectory.defaultWorkspaceId();
    void this.router.navigate(['/workspaces', target, 'documents']);
  }

  protected retryWorkspaceLoad(): void {
    this.workspaceDirectory.reload();
  }

  protected workspaceLink(path: string): string[] {
    const workspaceId = this.activeWorkspaceId() ?? DEFAULT_WORKSPACE_ID;
    return ['/workspaces', workspaceId, path];
  }

  private findWorkspace(id: string | null): WorkspaceSummary | null {
    if (!id) {
      return null;
    }
    return this.workspaces().find((workspace) => workspace.id === id) ?? null;
  }
}
