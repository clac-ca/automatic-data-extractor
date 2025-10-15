import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'ade-workspace-documents',
  standalone: true,
  templateUrl: './documents.component.html',
  styleUrl: './documents.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class WorkspaceDocumentsComponent {}
