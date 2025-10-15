import { Routes } from '@angular/router';

export const WORKSPACES_ROUTES: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'documents',
  },
  {
    path: 'documents',
    loadComponent: () =>
      import('./documents/documents.component').then(
        (m) => m.WorkspaceDocumentsComponent,
      ),
  },
];
