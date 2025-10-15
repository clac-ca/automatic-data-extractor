import { Routes } from '@angular/router';
import { AppShellComponent } from './core/layout/app-shell.component';
import { setupGuard } from './core/setup/setup.guard';

export const APP_ROUTES: Routes = [
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
        redirectTo: 'workspaces',
      },
      {
        path: 'workspaces',
        loadChildren: () =>
          import('./features/workspaces/workspaces.routes').then(
            (m) => m.WORKSPACES_ROUTES,
          ),
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
    redirectTo: 'workspaces',
  },
];
