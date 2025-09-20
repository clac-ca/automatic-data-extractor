---
Audience: Platform administrators, IT architects
Goal: Introduce ADE's architecture, shared terminology, and supporting references before diving into deployment or configuration workflows.
Prerequisites: Familiarity with ADE's mission and access to the backend repository for source lookups.
When to use: Use this section when evaluating ADE for approval, onboarding new maintainers, or preparing architecture reviews.
Validation: Follow the recommended reading order below and confirm each link resolves, including the glossary reference.
Escalate to: Lead platform administrator or architecture owner when core architecture documentation drifts from the running system.
---

# Foundation

This section sets the baseline for how ADE is assembled, what each component owns, and how jobs move through the system. It focuses on architectural choices that change infrequently so every other guide can rely on the same mental model. Start here before evaluating security controls, deployment variants, or configuration workflows.

## Recommended reading order

1. [System overview](./system-overview.md) — architecture summary, component responsibilities, integration surfaces, and job lifecycle.
2. [ADE glossary](../../ADE_GLOSSARY.md) — canonical definitions referenced across every guide.
3. Health and identifier notes in [Platform operations overview](../platform/README.md) — highlights deployment prerequisites referenced later.
4. Authentication and API credential plans in [Security](../security/README.md) when you are ready to review trust boundaries.

The foundation also outlines how data teams will authenticate once API key support lands and why configuration owners should prefer the built-in UI for day-to-day changes even though the same REST endpoints remain available.

Future additions will include configuration model deep dives and diagrams exported to [docs/assets](../assets/README.md).
