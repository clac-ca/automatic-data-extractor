import { CanMatchFn } from '@angular/router';

/**
 * Placeholder guard used to protect the `/setup` wizard route.
 *
 * Future phases will inject a setup service that interrogates the backend
 * to determine whether the initial administrator has been provisioned.
 */
export const setupGuard: CanMatchFn = () => {
  // TODO: replace stub with real bootstrap state check.
  return true;
};
