# Settings (.env / env vars / ade_engine.toml)

Precedence: defaults < `ade_engine.toml` < `.env` < env vars < init kwargs.

Fields (prefix `ADE_ENGINE_` for env):
- `config_package` (required) — path to the config package directory
- `append_unmapped_columns` (bool, default True)
- `unmapped_prefix` (default `raw_`)
- `mapping_tie_resolution` (`leftmost` | `drop_all`)
- `log_format` (`text`|`ndjson`)
- `log_level`

Examples:
```
# .env
ADE_ENGINE_APPEND_UNMAPPED_COLUMNS=false
ADE_ENGINE_UNMAPPED_PREFIX=raw_
```

`ade_engine.toml` may contain a top-level table or `[ade_engine]` table with the same keys.
