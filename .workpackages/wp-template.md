> **Agent Instructions (read first)**
>
> * Treat this work package as the **single source of truth** for this task.
> * Keep the checklist below up to date: change `[ ]` → `[x]` as tasks are completed, and add new items when new work is discovered.
> * Replace placeholders (`{{LIKE_THIS}}`) with concrete details as they become known.
> * Prefer small, incremental commits aligned to checklist items.
> * If the plan must change, **update this document first**, then update the code.

---

## Work Package Checklist

* [ ] {{TASK_1_SHORT_DESCRIPTION}}
* [ ] {{TASK_2_SHORT_DESCRIPTION}}
* [ ] {{TASK_3_SHORT_DESCRIPTION}}

> **Agent note:**
> Add or remove checklist items as needed. Keep brief status notes inline, for example:
> `- [x] {{TASK_SUMMARY}} — {{SHORT_STATUS_NOTE_OR_COMMIT_REF}}`

---

# {{WORK_PACKAGE_TITLE}}

## 1. Objective

**Goal:**
{{HIGH_LEVEL_GOAL_OF_THIS_WORK}}

You will:

* {{ACTION_1}}
* {{ACTION_2}}
* {{ACTION_3}}

The result should:

* {{EXPECTED_OUTCOME_1}}
* {{EXPECTED_OUTCOME_2}}
* {{EXPECTED_OUTCOME_3}}

---

## 2. Context (Starting point)

{{DESCRIPTION_OF_CURRENT_STATE}}

Include relevant background such as:

* Existing behavior or architecture
* Known issues or limitations
* Why this work is needed now

---

## 3. Target architecture / structure (ideal)

{{DESCRIPTION_OF_DESIRED_END_STATE}}

> **Agent instruction**
>
> * Keep this section in sync with reality.
> * If the design changes during implementation, update this section and the file tree below.

```text
{{ROOT_PATH}}/
  {{PATH_1}}    # {{WHAT_CHANGES_HERE}}
  {{PATH_2}}    # {{WHAT_CHANGES_HERE}}
  {{PATH_3}}    # {{WHAT_CHANGES_HERE}}
```

---

## 4. Design (for this work package)

### 4.1 Design goals

* {{DESIGN_GOAL_1}}
* {{DESIGN_GOAL_2}}
* {{DESIGN_GOAL_3}}

### 4.2 Key components / modules

* {{COMPONENT_OR_MODULE_1}} — {{RESPONSIBILITY}}
* {{COMPONENT_OR_MODULE_2}} — {{RESPONSIBILITY}}
* {{COMPONENT_OR_MODULE_3}} — {{RESPONSIBILITY}}

### 4.3 Key flows / pipelines

* {{FLOW_1_NAME}} — {{BRIEF_DESCRIPTION}}
* {{FLOW_2_NAME}} — {{BRIEF_DESCRIPTION}}

### 4.4 Open questions / decisions

* {{OPEN_QUESTION_OR_DECISION_1}}
* {{OPEN_QUESTION_OR_DECISION_2}}

> **Agent instruction:**
> When a decision is finalized, replace the placeholder with the decision and (optionally) a short rationale.

---

## 5. Implementation notes for agents

* {{IMPLEMENTATION_NOTE_1}}
* {{IMPLEMENTATION_NOTE_2}}
* {{IMPLEMENTATION_NOTE_3}}

Include constraints, testing notes, tooling limitations, or guidance that helps future contributors work safely and consistently.