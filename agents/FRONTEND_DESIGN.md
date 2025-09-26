# ADE frontend design

This document describes how the Automatic Data Extractor (ADE) web client should
look, feel, and stay aligned with the FastAPI backend. Treat it as the source of
truth for product scope, UX patterns, technical architecture, and directory
structure. Update it whenever the backend contracts or roadmap shift.

## Design Review (2025-09-26)

### What feels strong
- Comprehensive articulation of personas and IA keeps backend and UI aligned.
- Accessibility and calm-UI principles encourage consistent, audit-friendly interfaces.
- Clear route-to-endpoint mapping simplifies contract validation when consuming APIs.
- Proposed tooling stack (Vite, React, TypeScript, React Router, TanStack Query) matches mainstream practices and lowers onboarding cost.

### Where it overreaches today
- Scope assumes fully realised workspaces, document workflows, and configuration UIs that do not exist yet, making incremental delivery hard.
- Heavy reliance on persisted filters, status trays, and virtualised viewers adds complexity before we have basic CRUD working.
- Navigation shell (top bar, side rail, status tray) presumes settled visual language; rebuilding from scratch suggests we should defer these decisions.
- Route map spreads effort across six feature surfaces, which dilutes focus from the core sign-in -> documents flow we actually need first.

### Opportunities for the reboot
- Start by validating authentication, layout scaffolding, and data fetching conventions before layering rich domain UX.
- Treat workspace context, document-type filters, and advanced job flows as progressive enhancements added once APIs and user feedback demand them.
- Document minimal testing expectations (smoke-level) alongside feature scope so we regain confidence quickly.

## Minimal foundation for the restart


---

## MVP scope

Focus exclusively on the core authentication loop:

- `/login` route with email + password form, client-side validation, and accessible error feedback.
- Authenticated landing view that confirms success, shows the signed-in user email, and offers sign out. Future navigation lives behind this screen.

## Authentication flow details

[EXPLORE BACKEND API TO FIGURE OUT HOW AUTH WORKS]

## Security considerations

[EXPLORE BACKEND API TO FIGURE OUT HOW AUTH WORKS]


## Deferred features

The previous design covered admin bootstrap, navigation rails, workspace dashboards, document upload tooling, and results viewers. All of those remain out of scope until the authentication foundation is stable and reviewed.

