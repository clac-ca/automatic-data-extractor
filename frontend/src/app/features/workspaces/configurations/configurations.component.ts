import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-workspace-configurations',
  standalone: true,
  templateUrl: './configurations.component.html',
  styleUrl: './configurations.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfigurationsComponent {}
