## ADE Config Templates

`default_config/` is a vendored scaffold snapshot used by `ConfigStorage.materialize_from_template`.

### Manual refresh workflow

1. Run `cd backend && uv run python -m ade_engine config init <tmp_dir> --package-name ade_config --layout src`.
2. Replace `default_config/` with the generated scaffold output.
3. Review and update `default_config/pyproject.toml` to pin the desired `ade-engine` dependency.
4. Run backend tests and commit the updated template snapshot.
