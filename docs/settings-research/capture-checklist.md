# Microsoft Capture Checklist

Use this checklist during headed browser capture sessions on `admin.microsoft.com` and `entra.microsoft.com`.

## Required breakpoints

- `390` (mobile)
- `768` (tablet)
- `1024` (small desktop)
- `1280` (desktop)
- `1440` (wide desktop)

## Capture targets

- Settings/home shell
- Users list
- User detail/edit
- Groups list
- Group detail/edit
- Roles list
- Role detail/edit
- Authentication/SSO settings
- API keys page
- Run controls page
- Workspace list and workspace scoped settings pages

## State variants

- Default
- Hover/focus
- Selected row
- Loading
- Empty
- Error
- Unsaved changes
- Destructive confirmation

## Artifact naming convention

- `microsoft-<area>-<state>-<breakpoint>.png`
- Examples:
  - `microsoft-users-list-default-1280.png`
  - `microsoft-groups-detail-unsaved-1024.png`

## Notes template per capture

- URL
- Screen width
- Primary task on page
- Navigation structure
- Command/action placement
- Density and spacing notes
- Accessibility observations
- Transferable pattern (`yes/no`, reason)
