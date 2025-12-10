# Task 20 – Clean docs referencing manifest/module-string ordering

Checklist: F) Remove/replace old docs referring to TOML manifest columns ordering & module strings.

Objective: Update documentation to align with registry/discovery model and new output ordering rules.

Implementation steps:
- [ ] Search `docs/` and `apps/ade-engine/docs/` for mentions of `manifest.toml`, column ordering lists, or module-string wiring; replace with registry/discovery language.
- [ ] Update diagrams/snippets to show Python package structure instead of manifest blocks.
- [ ] Add short “what changed” note to `docs/ade-engine/legacy-removals.md` summarizing removals.

Definition of done:
- [ ] No doc pages instruct users to edit manifest for ordering/wiring; new docs point to decorators + hooks; build/bundle docs render without stale references.
