import { Injectable, PLATFORM_ID, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { isPlatformBrowser } from '@angular/common';
import { DEFAULT_WORKSPACE_ID } from '../constants';

const STORAGE_KEY = 'ade.setupComplete';

@Injectable({ providedIn: 'root' })
export class SetupStateService {
  private readonly platformId = inject(PLATFORM_ID);
  private readonly router = inject(Router);

  private readonly setupCompleteSignal = signal<boolean>(this.readInitialState());

  readonly setupComplete = this.setupCompleteSignal.asReadonly();
  readonly setupIncomplete = computed(() => !this.setupComplete());

  isSetupComplete(): boolean {
    return this.setupComplete();
  }

  markComplete(): void {
    if (this.setupComplete()) {
      return;
    }

    this.persist(true);
    this.setupCompleteSignal.set(true);
  }

  reset(): void {
    this.persist(false);
    this.setupCompleteSignal.set(false);
  }

  navigateToWorkspace(): void {
    void this.router.navigate(['/workspaces', DEFAULT_WORKSPACE_ID, 'documents']);
  }

  navigateToSetup(): void {
    void this.router.navigate(['/setup']);
  }

  private readInitialState(): boolean {
    if (!this.storageAvailable()) {
      return false;
    }

    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  }

  private persist(value: boolean): void {
    if (!this.storageAvailable()) {
      return;
    }

    try {
      localStorage.setItem(STORAGE_KEY, value ? 'true' : 'false');
    } catch {
      // Ignore storage failures; service will fall back to in-memory signal.
    }
  }

  private storageAvailable(): boolean {
    return isPlatformBrowser(this.platformId) && typeof localStorage !== 'undefined';
  }
}
