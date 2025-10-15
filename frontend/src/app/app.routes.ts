import { Routes } from '@angular/router';
import { AppShellComponent } from './core/layout/app-shell.component';
import { DEFAULT_WORKSPACE_ID } from './core/constants';
import { setupGuard } from './core/setup/setup.guard';

export const routes: Routes = [
  {
    path: 'setup',
    canMatch: [setupGuard],
    loadComponent: () =>
      import('./features/setup/setup.component').then((m) => m.SetupComponent),
  },
  {
    path: '',
    component: AppShellComponent,
    children: [
      {
        path: '',
        pathMatch: 'full',
        redirectTo: `workspaces/${DEFAULT_WORKSPACE_ID}/documents`,
      },
      {
        path: 'workspaces',
        children: [
          {
            path: '',
            pathMatch: 'full',
            redirectTo: `${DEFAULT_WORKSPACE_ID}/documents`,
          },
          {
            path: ':workspaceId',
            loadChildren: () =>
              import('./features/workspaces/workspaces.routes').then(
                (m) => m.WORKSPACES_ROUTES,
              ),
          },
        ],
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/settings/settings.component').then(
            (m) => m.SettingsComponent,
          ),
      },
    ],
  },
  {
    path: '**',
    redirectTo: `workspaces/${DEFAULT_WORKSPACE_ID}/documents`,
  },
];
