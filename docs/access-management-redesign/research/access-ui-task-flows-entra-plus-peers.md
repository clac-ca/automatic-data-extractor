# Access UI Task Flows (Entra + 4 Peer Benchmark)

Date: February 12, 2026

## Purpose

Document benchmark task flows across Microsoft Entra, Okta, Google Workspace Admin,
GitHub Enterprise, and Atlassian Admin to inform ADE's access-management UI redesign.

This research is task-first (not product-first) and focuses on reducing admin task
switching and ambiguity.

## Benchmark Method

1. Collect only official vendor documentation.
2. Normalize each vendor into the same access tasks.
3. Extract interaction patterns, permission boundaries, and read-only behavior.
4. Record implications for ADE org/workspace surfaces.

## Task Set

1. `T1` Create user and assign access in one flow.
2. `T2` Add/remove members from a group from group detail.
3. `T3` Add/remove group memberships from user detail.
4. `T4` Assign users/groups to scoped roles or app access.
5. `T5` Perform bulk membership operations safely.
6. `T6` Handle provider-managed groups and sync constraints.
7. `T7` Communicate permission boundaries and delegated admin behavior.

## Flow Findings by Task

### T1: Create user + assign access

1. Entra: user creation supports rich profile plus groups/roles in creation-related
   workflows; enterprise-app assignment uses a single add-assignment pane for
   principal and role selection.
2. Okta: manual user creation supports optional groups in create flow.
3. GitHub: org add/invite flow supports role and optional team at invitation time.
4. Atlassian: user role grants are grouped under grant access actions and default groups.
5. Google: user-to-group assignment is available from user account pages.

Implication for ADE:

1. Keep assignment in create flow and avoid "create first, assign later" for primary
   access paths.

### T2: Group detail membership management

1. Entra: group detail pages support explicit `Members` and `Owners` management with
   add/remove actions.
2. Okta: group pages support manual assignment/removal of people.
3. Google: group pages support add members and role changes; dynamic groups block
   manual member edits.
4. Atlassian: group profile supports add/remove members and grant app roles.
5. GitHub teams: team membership managed in team settings unless team is IdP-synced.

Implication for ADE:

1. Group detail must be first-class with both member and owner operations for
   internally managed groups.

### T3: User detail membership management

1. Google: user account page includes `Groups` and `Add user to groups`.
2. Entra patterns and Graph membership APIs support user-centric membership views and
   membership operations in admin workflows.
3. Okta and Atlassian emphasize group-centric edits but still expose user-centric
   access controls.

Implication for ADE:

1. Support both surfaces: group-centric and user-centric membership editing.
2. Do not force admins to navigate away from user detail to manage memberships.

### T4: Scoped assignment UX

1. Entra: add assignment pane combines principal selection with role selection.
2. Okta: app assignment tabs separate users vs groups but keep assignment actions
   in one context.
3. GitHub: invitation supports org role and optional team in one flow.
4. Atlassian: group/app roles and admin roles are grantable with explicit role tables.

Implication for ADE:

1. Keep a single add-assignment drawer grammar across org/workspace surfaces:
   principal + role + scope.

### T5: Bulk membership operations

1. Entra: group membership bulk import/remove via CSV, explicit operation entrypoints,
   and status tracking.
2. Google: group member lists and operations support large-list administration via API
   and admin tooling.
3. GitHub/Okta/Atlassian generally bias toward list-level bulk patterns and delegated
   automation for larger scale.

Implication for ADE:

1. Put bulk actions in command bars and report partial results clearly.
2. For group members, support at least safe multi-select add/remove and optional file
   import later.

### T6: Provider-managed groups and sync

1. GitHub team sync: once linked to IdP group, membership edits must happen in IdP,
   not GitHub.
2. Okta Group Push: downstream group membership expects source-of-truth discipline;
   assignment and push constraints are explicit.
3. Atlassian SCIM groups are read-only in Atlassian and managed in IdP.
4. Google dynamic groups block manual add and require query updates.

Implication for ADE:

1. IdP or dynamic groups must show read-only membership controls with explicit reason
   and next-step guidance.

### T7: Permission boundaries and delegated admin UX

1. Entra docs consistently tie actions to explicit admin roles.
2. Okta has narrowly scoped delegated roles (group admin, group membership admin).
3. Atlassian distinguishes organization admin, site admin, and user access admin.
4. Google maps privileges through predefined/custom admin roles and groups privileges.

Implication for ADE:

1. Disabled/hidden action behavior must be deterministic by permission and include
   explanatory text.
2. Workspace owners should have workspace-scoped member management actions without
   org-wide user administration actions.

## Inferences (Explicit)

1. Inference: products that scale well expose both group-centric and user-centric
   membership operations to reduce click depth and context switching.
2. Inference: first-class UX requires visible scope boundaries in every action surface,
   not only at backend authorization time.

## Sources

1. [How to create, invite, and delete users (Entra)](https://learn.microsoft.com/en-us/entra/fundamentals/how-to-create-delete-users)
2. [Manage users and groups assignment to an application (Entra)](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/assign-user-or-group-access-portal)
3. [User management enhancements (Entra)](https://learn.microsoft.com/en-us/entra/identity/users/users-search-enhanced)
4. [How to manage groups (Entra)](https://learn.microsoft.com/en-gb/azure/active-directory/fundamentals/how-to-manage-groups)
5. [Bulk add group members (Entra)](https://learn.microsoft.com/en-us/azure/active-directory/enterprise-users/groups-bulk-import-members)
6. [Bulk remove group members (Entra)](https://learn.microsoft.com/en-us/entra/identity/users/groups-bulk-remove-members)
7. [Manage rules for dynamic membership groups (Entra)](https://learn.microsoft.com/en-us/entra/identity/users/groups-dynamic-membership)
8. [Group administrators (Okta)](https://help.okta.com/oie/en-us/content/topics/security/administrators-group-admin.htm)
9. [Group membership administrators (Okta)](https://help.okta.com/en-us/content/topics/security/administrators-group-membership-admin.htm)
10. [Add users manually (Okta)](https://help.okta.com/en-us/Content/Topics/users-groups-profiles/usgp-add-users.htm)
11. [Manually assign people to a group (Okta)](https://help.okta.com/en-us/Content/Topics/users-groups-profiles/usgp-assign-group-people.htm)
12. [Group Push prerequisites (Okta)](https://help.okta.com/en-us/content/topics/users-groups-profiles/usgp-group-push-prerequisites.htm)
13. [Manage app integration assignments (Okta)](https://help.okta.com/en-us/Content/Topics/Apps/apps-manage-assignments.htm)
14. [Inviting users to join your organization (GitHub)](https://docs.github.com/organizations/managing-membership-in-your-organization/inviting-users-to-join-your-organization)
15. [Adding people to your organization (GitHub)](https://docs.github.com/en/organizations/managing-membership-in-your-organization/adding-people-to-your-organization)
16. [Synchronizing a team with an IdP group (GitHub)](https://docs.github.com/enterprise-cloud%40latest/organizations/organizing-members-into-teams/synchronizing-a-team-with-an-identity-provider-group)
17. [What are the different types of admin roles? (Atlassian)](https://support.atlassian.com/user-management/docs/what-are-the-different-types-of-admin-roles/)
18. [Edit a group (Atlassian)](https://support.atlassian.com/user-management/docs/edit-a-group/)
19. [Give users admin permissions (Atlassian)](https://support.atlassian.com/user-management/docs/give-users-admin-permissions/)
20. [Understand user provisioning (Atlassian)](https://support.atlassian.com/provisioning-users/docs/understand-user-provisioning/)
21. [Add or invite users to a group (Google Workspace)](https://support.google.com/cloudidentity/answer/9400087?hl=en)
22. [Can't add a user to a group (Google Workspace)](https://support.google.com/a/answer/9242708?hl=en)
23. [Manage membership automatically with dynamic groups (Google Workspace)](https://support.google.com/a/answer/10286834?hl=en)
24. [Groups administrator FAQ (Google Workspace)](https://support.google.com/a/answer/167085?hl=en)
25. [Directory API: Group Members (Google)](https://developers.google.com/workspace/admin/directory/v1/guides/manage-group-members)
