# Proposed next frontend milestone

## Objective
Wire the ADE frontend to the real workspace endpoints by replacing mocked data with authenticated API calls and introducing a basic auth hand-off to the FastAPI backend.

## Why this matters
- The UI currently surfaces mocked workspace data, which prevents validating backend integrations.
- Implementing the actual fetch flow will de-risk subsequent feature work that depends on live workspace metadata (documents, jobs, configurations).

## Suggested scope
1. Implement a lightweight auth context that exchanges stored credentials (or a temporary token) for a FastAPI session and persists it securely.
2. Replace the mocked React Query hooks with real `GET /workspaces` and `GET /workspaces/{workspaceId}` requests, handling error states and unauthorized responses.
3. Add loading and empty states backed by real API responses, including toast notifications for failures.
4. Update the workspace switcher to allow the user to select among the fetched workspaces and persist the selection (local storage or query param) between navigations.
5. Extend Vitest coverage with mocks verifying the hooks surface success, error, and empty states correctly.

## Definition of done
- Users can sign in using the temporary auth flow and see their real workspaces.
- Navigating between workspaces updates the workspace context queries without page reloads.
- Unit tests cover the success and failure paths for the React Query hooks and workspace switcher state management.
