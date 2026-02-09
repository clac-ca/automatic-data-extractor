---
name: workpackage-executor
description: Execute workpackages as the source of truth. Use when asked to start, implement, or advance a workpackage, break work into stages, update checklists, and keep the workpackage current during execution.
---

# Workpackage Executor

## Overview
Execute tasks described in workpackages, break work into stages as needed, and keep the workpackage updated before and after code changes.

## Workflow
1. Locate the workpackage under `workpackages/<wp-id>-<slug>/workpackage.md`.
2. Read the document first and restate plan, scope, and open questions.
3. If the plan needs staging, add or update the WBS structure to reflect stages and dependencies.
4. If any plan change is required, update the workpackage before editing code.
5. As tasks complete, flip checklist items from `[ ]` to `[x]` and keep acceptance criteria aligned.
6. For rollups, update subpackage checklists and roll up status in the top-level file.

## Staging rules
- Stage by major checklist sections or dependency boundaries.
- Each stage should be independently testable and have clear acceptance criteria.