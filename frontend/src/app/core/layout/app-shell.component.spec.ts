import { ComponentFixture, TestBed } from '@angular/core/testing';
import { computed, signal } from '@angular/core';
import { provideRouter, Router, Routes, NavigationEnd } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { filter, take } from 'rxjs/operators';
import { AppShellComponent } from './app-shell.component';
import { DocumentsComponent } from '../../features/workspaces/documents/documents.component';
import { SettingsComponent } from '../../features/settings/settings.component';
import { WorkspaceDirectoryService, WorkspaceSummary } from '../workspaces/workspace-directory.service';
import { DEFAULT_WORKSPACE_ID } from '../constants';

const TEST_ROUTES: Routes = [
  { path: 'workspaces/:workspaceId/documents', component: DocumentsComponent },
  { path: 'settings', component: SettingsComponent },
];

class WorkspaceDirectoryServiceStub {
  private readonly workspaceList = signal<WorkspaceSummary[]>([
    { id: 'demo-workspace', name: 'Demo Workspace' },
    { id: 'operations', name: 'Operations' },
  ]);

  readonly workspaces = computed(() => this.workspaceList());
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly hasWorkspaces = computed(() => this.workspaceList().length > 0);
  readonly defaultWorkspaceId = computed(
    () => this.workspaceList()[0]?.id ?? DEFAULT_WORKSPACE_ID,
  );

  initialise = jasmine.createSpy('initialise');
  reload = jasmine.createSpy('reload');

  setWorkspaces(workspaces: WorkspaceSummary[]): void {
    this.workspaceList.set(workspaces);
  }

  setLoading(loading: boolean): void {
    this.loading.set(loading);
  }

  setError(error: string | null): void {
    this.error.set(error);
  }
}

describe('AppShellComponent', () => {
  let router: Router;
  let workspaceDirectory: WorkspaceDirectoryServiceStub;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppShellComponent, DocumentsComponent, SettingsComponent],
      providers: [
        provideRouter(TEST_ROUTES),
        { provide: WorkspaceDirectoryService, useClass: WorkspaceDirectoryServiceStub },
      ],
    }).compileComponents();

    router = TestBed.inject(Router);
    workspaceDirectory = TestBed.inject(
      WorkspaceDirectoryService,
    ) as unknown as WorkspaceDirectoryServiceStub;
    await router.navigateByUrl('/');
  });

  function waitForNextNavigation(predicate: (event: NavigationEnd) => boolean = () => true) {
    return firstValueFrom(
      router.events.pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd && predicate(event)),
        take(1),
      ),
    );
  }

  async function createComponent(initialUrl: string): Promise<ComponentFixture<AppShellComponent>> {
    await router.navigateByUrl(initialUrl);
    const fixture = TestBed.createComponent(AppShellComponent);
    fixture.detectChanges();
    return fixture;
  }

  it('creates the shell for a workspace route and reflects the current workspace', async () => {
    const fixture = await createComponent('/workspaces/demo-workspace/documents');
    expect(workspaceDirectory.initialise).toHaveBeenCalled();
    expect(fixture.componentInstance).toBeTruthy();
    const workspaceName = fixture.nativeElement.querySelector('.app-shell__workspace-name');
    expect(workspaceName?.textContent).toContain('Demo Workspace');
    const select: HTMLSelectElement | null = fixture.nativeElement.querySelector('.app-shell__workspace-select');
    expect(select?.value).toBe('demo-workspace');
  });

  it('toggles the sidebar when workspace navigation is visible', async () => {
    const fixture = await createComponent('/workspaces/demo-workspace/documents');
    const toggleButton: HTMLButtonElement | null = fixture.nativeElement.querySelector('.app-shell__sidebar-toggle');
    expect(toggleButton).not.toBeNull();
    expect(toggleButton!.disabled).toBeFalse();
    toggleButton!.click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.app-shell').classList).toContain('app-shell--sidebar-collapsed');
  });

  it('navigates when a different workspace is selected', async () => {
    const fixture = await createComponent('/workspaces/demo-workspace/documents');
    const select: HTMLSelectElement | null = fixture.nativeElement.querySelector('.app-shell__workspace-select');
    expect(select).not.toBeNull();
    const navigationPromise = waitForNextNavigation((event) => event.urlAfterRedirects.includes('/workspaces/operations/documents'));
    select!.value = 'operations';
    select!.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await navigationPromise;
    expect(router.url).toBe('/workspaces/operations/documents');
  });

  it('hides workspace navigation when viewing non-workspace routes', async () => {
    const fixture = await createComponent('/settings');
    const sidebar = fixture.nativeElement.querySelector('.app-shell__sidebar');
    expect(sidebar).toBeNull();
    const toggleButton: HTMLButtonElement | null = fixture.nativeElement.querySelector('.app-shell__sidebar-toggle');
    expect(toggleButton?.disabled).toBeTrue();
  });

  it('displays workspace load errors and allows retrying', async () => {
    const fixture = await createComponent('/workspaces/demo-workspace/documents');
    workspaceDirectory.setError('Failed to load workspaces.');
    workspaceDirectory.setLoading(false);
    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('.app-shell__workspace-status--error');
    expect(alert?.textContent).toContain('Failed to load workspaces');

    const retryButton: HTMLButtonElement | null = fixture.nativeElement.querySelector(
      '.app-shell__workspace-retry',
    );
    expect(retryButton).not.toBeNull();
    retryButton!.click();
    expect(workspaceDirectory.reload).toHaveBeenCalled();
  });
});
