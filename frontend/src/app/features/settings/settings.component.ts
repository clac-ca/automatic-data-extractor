import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'ade-settings',
  standalone: true,
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SettingsComponent {}
