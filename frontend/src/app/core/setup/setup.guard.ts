import { CanMatchFn } from '@angular/router';

/**
 * Placeholder guard protecting the first-run /setup flow.
 *
 * Later phases will replace the stub logic with a call into
 * the backend to determine whether an initial admin exists.
 */
export const setupGuard: CanMatchFn = () => {
  // TODO: inject SetupService to determine when the guard should allow navigation.
  return true;
};
