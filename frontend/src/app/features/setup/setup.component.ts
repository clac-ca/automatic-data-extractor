import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
  selector: 'app-setup',
  standalone: true,
  templateUrl: './setup.component.html',
  styleUrl: './setup.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SetupComponent {}
