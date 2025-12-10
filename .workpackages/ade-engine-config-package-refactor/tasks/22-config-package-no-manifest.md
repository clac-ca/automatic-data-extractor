# Task 22 – Config package: remove manifest.toml requirement

Checklist: G) Remove `manifest.toml` requirement.

Objective: Ensure config packages function with only Python files registered via decorators; manifest files become optional/ignored.

Implementation steps:
- [ ] Update engine loader to never look for `manifest.toml` when using registry path; remove errors/warnings expecting it.
- [ ] Adjust template `config_package_example` to omit manifest, leaving `settings.toml` optional for engine settings only.
- [ ] Document in `docs/config-package-conventions.md` and template README that manifest is not required.

Definition of done:
- [ ] Engine runs example config package without manifest; docs/templates make no mention of required manifest.
