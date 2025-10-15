import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router, Routes, NavigationEnd } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { filter, take } from 'rxjs/operators';
import { AppShellComponent } from './app-shell.component';
import { DocumentsComponent } from '../../features/workspaces/documents/documents.component';
import { SettingsComponent } from '../../features/settings/settings.component';

const TEST_ROUTES: Routes = [
  { path: 'workspaces/:workspaceId/documents', component: DocumentsComponent },
  { path: 'settings', component: SettingsComponent },
];

describe('AppShellComponent', () => {
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppShellComponent, DocumentsComponent, SettingsComponent],
      providers: [provideRouter(TEST_ROUTES)],
    }).compileComponents();

    router = TestBed.inject(Router);
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
    expect(fixture.componentInstance).toBeTruthy();
    const workspaceName = fixture.nativeElement.querySelector('.app-shell__workspace-name');
    expect(workspaceName?.textContent).toContain('demo-workspace');
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
});
