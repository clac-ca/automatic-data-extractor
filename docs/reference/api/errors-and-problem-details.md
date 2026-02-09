# Errors and Problem Details

## Purpose

Describe ADE API error payload conventions and common remediation paths.

## Error Envelope

ADE uses Problem Details style responses for many non-2xx results.

Typical media type:

- `application/problem+json`

Typical fields:

- `type`: URI-like identifier for error category
- `title`: short error label
- `status`: HTTP status code
- `detail`: optional human-readable explanation
- `instance`: request instance path
- `requestId`: server-side request correlation ID
- `errors`: optional field-level details

## Shared Response Headers

- `X-Request-Id`: request correlation identifier for support and tracing
- `ETag`: present on select read responses that support optimistic concurrency

## Common Status Codes

| Status | Meaning | Typical cause | Common fix |
| --- | --- | --- | --- |
| `400` | Bad Request | malformed JSON/form/query payload | validate payload shape and field names |
| `401` | Unauthorized | missing/revoked/invalid API key or session | send valid `X-API-Key` or refresh auth |
| `403` | Forbidden | auth present but permission/CSRF requirement not met | grant required role/scope, include CSRF where needed |
| `404` | Not Found | workspace/resource not found in scope | verify identifiers and workspace access |
| `409` | Conflict | state transition not allowed | re-read resource state and retry valid transition |
| `412` | Precondition Failed | stale `If-Match` token | fetch latest ETag and retry |
| `413` | Content Too Large | upload exceeds configured limit | reduce file/archive size |
| `415` | Unsupported Media Type | requested preview/worksheet feature unsupported | use compatible file type or fallback route |
| `422` | Unprocessable Content | payload validates structurally but violates rules | fix semantic validation issues |
| `428` | Precondition Required | concurrency header required | include `If-Match`/`If-None-Match` as required |
| `429` | Too Many Requests | request throttled | retry with backoff |

## Example Problem Details Payload

```json
{
  "type": "https://ade.dev/problems/validation",
  "title": "Validation failed",
  "status": 422,
  "detail": "run_options cannot combine activeSheetOnly and inputSheetNames",
  "instance": "/api/v1/workspaces/01J.../documents",
  "requestId": "req_01J...",
  "errors": [
    {
      "path": "run_options.activeSheetOnly",
      "message": "activeSheetOnly cannot be combined with inputSheetNames",
      "code": "invalid_combination"
    }
  ]
}
```

## Concurrency Notes

Some endpoints require ETag-based optimistic concurrency:

- Read endpoint returns `ETag`.
- Mutation endpoint requires `If-Match`.
- Server returns `412` or `428` when tokens are stale/missing.

## Related Pages

- [Authentication](authentication.md)
- [Workspaces](workspaces.md)
- [Configurations](configurations.md)
- [Documents](documents.md)
- [Runs](runs.md)
