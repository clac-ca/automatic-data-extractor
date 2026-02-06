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
4. verify key paths from `docs/index.md`

## Local Checks

```bash
npx --yes markdownlint-cli2 "docs/**/*.md" "README.md" "CONTRIBUTING.md" "backend/**/README.md"
FILES="$(find docs -type f -name '*.md' -print) README.md CONTRIBUTING.md $(find backend -mindepth 2 -maxdepth 2 -name README.md -print)"
lychee --config .lychee.toml --no-progress $FILES
```

## Done Criteria

Docs are done when:

- new behavior is documented
- links are valid
- required settings are explicit
- troubleshooting guidance covers new failure cases
