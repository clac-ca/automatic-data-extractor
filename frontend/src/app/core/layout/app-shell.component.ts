import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { NgClass } from '@angular/common';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { DEFAULT_WORKSPACE_ID, DEMO_WORKSPACES, WorkspaceOption } from '../constants';

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
export class AppShellComponent {
  private static readonly WORKSPACE_ROUTE_PATTERN = /^\/workspaces\/([^/]+)/;

  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly sidebarOpen = signal(true);
  private readonly currentUrl = signal(this.router.url);

  protected readonly defaultWorkspaceId = DEFAULT_WORKSPACE_ID;
  protected readonly workspaceOptions: WorkspaceOption[] = DEMO_WORKSPACES;

  protected readonly currentWorkspaceId = computed(() => {
    const match = AppShellComponent.WORKSPACE_ROUTE_PATTERN.exec(
      this.currentUrl(),
    );
    return match ? decodeURIComponent(match[1]) : null;
  });

  protected readonly workspaceNavVisible = computed(
    () => this.currentWorkspaceId() !== null,
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

  toggleSidebar(): void {
    if (!this.workspaceNavVisible()) {
      return;
    }
    this.sidebarOpen.update((value) => !value);
  }

  protected onWorkspaceSelect(workspaceId: string): void {
    const target = workspaceId || DEFAULT_WORKSPACE_ID;
    void this.router.navigate(['/workspaces', target, 'documents']);
  }

  protected workspaceLink(path: string): string[] {
    const workspaceId = this.currentWorkspaceId() ?? DEFAULT_WORKSPACE_ID;
    return ['/workspaces', workspaceId, path];
  }
}
