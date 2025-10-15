import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { WorkspaceDirectoryService, WorkspaceSummary } from './workspace-directory.service';

describe('WorkspaceDirectoryService', () => {
  let service: WorkspaceDirectoryService;
  let httpTestingController: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [WorkspaceDirectoryService, provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(WorkspaceDirectoryService);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('loads workspaces once initialised', () => {
    const response: WorkspaceSummary[] = [
      { id: 'demo-workspace', name: 'Demo Workspace' },
      { id: 'operations', name: 'Operations' },
    ];

    service.initialise();

    const request = httpTestingController.expectOne('/api/v1/workspaces');
    expect(service.loading()).toBeTrue();

    request.flush(response);

    expect(service.loading()).toBeFalse();
    expect(service.status()).toBe('loaded');
    expect(service.workspaces()).toEqual(response);
    expect(service.hasWorkspaces()).toBeTrue();
    expect(service.defaultWorkspaceId()).toBe('demo-workspace');
  });

  it('retains the previous workspaces when a reload fails', () => {
    const response: WorkspaceSummary[] = [
      { id: 'demo-workspace', name: 'Demo Workspace' },
    ];

    service.initialise();
    const request = httpTestingController.expectOne('/api/v1/workspaces');
    request.flush(response);

    service.reload();

    const retry = httpTestingController.expectOne('/api/v1/workspaces');
    retry.flush(
      { detail: 'Something went wrong.' },
      { status: 500, statusText: 'Server Error' },
    );

    expect(service.status()).toBe('error');
    expect(service.error()).toContain('Something went wrong');
    expect(service.workspaces()).toEqual(response);
  });

  it('presents a useful message when the backend is unreachable', () => {
    service.initialise();

    const request = httpTestingController.expectOne('/api/v1/workspaces');
    request.error(new ProgressEvent('error'), {
      status: 0,
      statusText: 'Unknown Error',
    });

    expect(service.status()).toBe('error');
    expect(service.error()).toContain('Unable to reach the server');
  });
});
