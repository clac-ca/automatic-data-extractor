# Schema Index

This folder is the source of truth for structures referenced throughout the developer docs.

- `artifact.v1.1.schema.json` — run artifact schema (`tables[].mapping`, `pass_history`, summaries).
- `manifest.v0.6.schema.json` — config package manifest used by the CLI and backend.
- `config-package.index.v1.schema.json` — index produced by `ade api types` for discovery APIs.

## Validate quickly
Use any JSON Schema validator. Two options:

```bash
npm exec ajv-cli validate -s artifact.v1.1.schema.json -d path/to/artifact.json
python -m jsonschema -F cli artifact.v1.1.schema.json path/to/artifact.json
```

## Versioning
- Bump the `...vX.Y` portion of the filename when introducing breaking changes.
- Update `artifact_version` / `schema` fields in emitting code and docs at the same time.

## References
- Artifact fields: see [`../04-pass-map-columns-to-target-fields.md`](../04-pass-map-columns-to-target-fields.md)
- Manifest fields: see [`../01-config-packages.md`](../01-config-packages.md)
