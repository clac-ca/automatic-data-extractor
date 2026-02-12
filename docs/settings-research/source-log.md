# Source Log

## Primary Microsoft references

- Microsoft Teams admin model: [Manage settings and policies in Teams](https://learn.microsoft.com/en-us/microsoftteams/manage-settings-and-policies)
  - Key signal: unify admin surfaces through a task-oriented left navigation and policy hierarchy.
- Microsoft Services Hub admin center: [Admin Center (Customer + Workspaces)](https://learn.microsoft.com/en-us/services-hub/admin-center)
  - Key signal: separate organization-level controls from workspace-level controls in one console shell.
- Power BI workspace/admin settings entry patterns: [Workspace roles and permissions](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-roles-new-workspaces)
  - Key signal: workspace-specific security/actions should be contextualized by workspace identity.
- Fluent 2 nav guidance: [Navigation usage](https://fluent2.microsoft.design/components/web/react/core/nav/usage)
  - Key signal: persistent left nav with grouped sections and clear active state.
- Fluent 2 command actions: [Toolbar usage](https://fluent2.microsoft.design/components/web/react/core/toolbar/usage)
  - Key signal: action prominence should live in command rows near list/detail headers.

## Secondary enterprise UX references

- IBM Carbon form/edit flow: [Edit and review pattern](https://carbondesignsystem.com/patterns/edit-and-review-pattern/)
  - Key signal: full-page edit flow when field volume and task complexity are high.
- IBM Carbon data tables: [Data table usage](https://carbondesignsystem.com/components/data-table/usage/)
  - Key signal: high-density list views with explicit filtering and row actions.
- GitHub Primer layout guidance: [Split page layouts](https://primer.style/ui-patterns/page-layouts/split-page-layouts)
  - Key signal: predictable shell + content hierarchy and responsive behavior for complex admin tasks.
- Vercel team access docs: [Manage team members and roles](https://vercel.com/docs/accounts/team-management/managing-team-members)
  - Key signal: access control lists should prioritize quick edit actions and clear role visualization.

## ADE internal baseline references

- `/Users/justinkropp/.codex/worktrees/2d0e/automatic-data-extractor/frontend/src/pages/Workspace/sections/Documents/list/DocumentsListPage.tsx`
- `/Users/justinkropp/.codex/worktrees/2d0e/automatic-data-extractor/frontend/src/pages/Workspace/sections/Documents/list/table/DocumentsTableContainer.tsx`
- `/Users/justinkropp/.codex/worktrees/2d0e/automatic-data-extractor/frontend/src/pages/Workspace/sections/Documents/detail/DocumentsDetailPage.tsx`

These internal pages define ADE’s quality bar for density, layout stability, and command visibility.
