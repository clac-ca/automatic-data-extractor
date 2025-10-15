import { Routes } from '@angular/router';
import { DocumentsComponent } from './documents/documents.component';

export const WORKSPACES_ROUTES: Routes = [
  {
    path: '',
    redirectTo: 'documents',
    pathMatch: 'full',
  },
  {
    path: 'documents',
    component: DocumentsComponent,
  },
  {
    path: 'configurations',
    loadComponent: () =>
      import('./configurations/configurations.component').then(
        (m) => m.ConfigurationsComponent,
      ),
  },
  {
    path: 'jobs',
    loadComponent: () => import('./jobs/jobs.component').then((m) => m.JobsComponent),
  },
];
