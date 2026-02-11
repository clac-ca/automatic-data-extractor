# Documentation Maintenance

## Goal

Define when docs must be updated and how to validate docs changes.

## Update Triggers

Update docs whenever these change:

- commands or command flags
- environment variable behavior
- deployment/startup flow
- run lifecycle/retry behavior
- auth/security behavior
- release workflow

## PR Checklist

1. update affected docs pages
2. fix or update links
3. run docs checks locally
4. verify key paths from `docs/README.md`

## Local Checks

```bash
DOCS_FILES="$(find docs -type f -name '*.md' ! -path 'docs/audits/*' -print)"
npx --yes markdownlint-cli2 --config .docs.markdownlint-cli2.jsonc $DOCS_FILES
python3 scripts/docs/check_api_docs_coverage.py
```

Docs lint configuration is defined in `.docs.markdownlint-cli2.jsonc`.

If `lychee` is installed locally, you can optionally run link checks:

```bash
FILES="$(find docs -type f -name '*.md' -print) README.md CONTRIBUTING.md $(find backend -mindepth 2 -maxdepth 2 -name README.md -print)"
lychee --no-progress $FILES
```

## Done Criteria

Docs are done when:

- new behavior is documented
- links are valid
- required settings are explicit
- troubleshooting guidance covers new failure cases
