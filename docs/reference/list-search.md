# List Search (`q`)

The `q` query parameter provides consistent, server-side free-text search on list
endpoints. It is a filter (it does not change sort order) and is combined with
scope and filter DSL predicates.

## Semantics

- Normalize: trim leading/trailing whitespace and collapse internal whitespace to
  single spaces.
- Tokenize on whitespace.
- Drop tokens shorter than 2 characters.
- Match case-insensitive substrings.
- Combine tokens with AND; combine fields with OR.

Example:

`q=acme invoice` means:

- `acme` must match at least one searchable field
- `invoice` must match at least one searchable field

## Guardrails

- Max length: 200 characters (422 if exceeded)
- Max tokens: 8 (422 if exceeded)

## Escaping

`%` and `_` are treated literally (they are escaped in the underlying `ILIKE`
expression).

## Searchable Fields by Resource

- documents: `name`, `status`, `uploaderName`, `uploaderEmail`, `tags`
- runs: `id`, `status`, `configurationId`, `inputFilename`
- configurations: `displayName`, `status`
- builds: `id`, `status`, `summary`, `errorMessage`
- users: `email`, `displayName`
- apikeys: `name`, `prefix`
- workspaces: `name`, `slug`
- members: `userId`, `roleSlugs`
- roles: `name`, `slug`, `description`
- permissions: `key`, `resource`, `action`, `label`
- roleassignments: `userId`, `roleSlug`, `scopeType`, `scopeId`
