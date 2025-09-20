---
Audience: Support teams, Configuration managers
Goal: Provide step-by-step instructions for publishing a configuration revision and rolling back safely when needed.
Prerequisites: Access to the configuration UI (or API access with configuration edit permissions) and clarity on the target document type.
When to use: Follow when promoting a draft to active status or reverting to a previous revision after an incident.
Validation: Confirm new revisions appear via `GET /configurations`, check active resolution, run a smoke-test job, and inspect emitted events.
Escalate to: Platform administrator when no active configuration exists or promotions fail repeatedly with conflicts.
---

# Publishing and rollback

Publishing a configuration changes how ADE processes documents, so treat each promotion as a controlled change. Use the configuration UI whenever possible so guard rails (role checks, previews, confirmation modals) stay in place. The API endpoints referenced below live in `backend/app/routes/configurations.py` and use schemas from `backend/app/schemas.py` for teams that automate deployments.

## Publish a draft

Publishing a configuration changes how ADE processes documents, so treat each promotion as a controlled change. Most teams ship revisions through the configuration UI, which immediately shows the impacted events and activation status. The equivalent API calls remain documented for automation.

### Preferred UI path

1. Open **Configuration → Drafts**, select the draft, and edit metadata or payload fields inline.
2. Use **Preview events** to confirm the history looks correct (you should see `configuration.created` and any follow-up updates).
3. Click **Activate revision**, acknowledge the confirmation, and note the new `activated_at` timestamp shown in the sidebar.
4. Run a smoke-test job from the **Jobs → New job** modal to verify behaviour before leaving the page.

### Equivalent API calls

```json
POST /configurations
{
  "document_type": "invoice",
  "title": "Invoice extraction v3",
  "payload": { "rules": [...] },
  "is_active": false
}

PATCH /configurations/{configuration_id}
{ "is_active": true }

GET /configurations/active/invoice
GET /configurations/{configuration_id}/events
```

Follow the same validation pattern as the UI by running a smoke job (`POST /jobs`) and confirming events include `configuration.activated`.

## Roll back to a previous revision

### Preferred UI path

1. Open **Configuration → Revisions**, filter by document type, and locate the last known-good version.
2. Choose **Activate this revision**. ADE records `configuration.activated` and demotes the previously active revision automatically.
3. Capture the reason for rollback in your change log (include the request ID shown in the UI footer).
4. Run the same smoke-test job you used during publish to confirm behaviour has stabilised.

### Equivalent API calls

```json
GET /configurations?document_type=invoice
PATCH /configurations/{configuration_id}
{ "is_active": true }

POST /jobs
{
  "document_id": "...",
  "document_type": "invoice"
}
```

Finish by repeating the publish validation steps: resolve the active configuration, inspect events, and document the rollback outcome.

## When activation fails

- **409 Conflict:** Another active revision exists for the document type. Refresh the list and ensure you are activating the intended revision (someone else may have promoted a change).
- **404 Not Found:** The configuration ID is invalid or the revision was deleted. Confirm you are targeting a draft/retired revision.
- **422 Validation:** Payload schema mismatch. Re-run local validation before publishing.

## Escalation criteria

Escalate to platform administrators when:

- `GET /configurations/active/{document_type}` returns 404 for a document type in use.
- Activation repeatedly fails because `configuration.activated` events show the wrong revision being promoted (indicates automation race condition).
- Smoke-test jobs fail consistently after promotion and quick rollback attempts do not stabilise the system.
