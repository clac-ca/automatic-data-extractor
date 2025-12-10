# Task 16 – Settings implementation (pydantic-settings)

Checklist: E) Implement `ade_engine.settings.Settings` via `pydantic_settings` with precedence defaults < TOML < `.env` < env vars < init kwargs; keys: `append_unmapped_columns`, `unmapped_prefix`, `mapping_tie_resolution`, etc.

Objective: Centralize engine toggles using `BaseSettings`, supporting `.env`, `ade_engine.toml`, env vars, and kwargs.

Implementation steps:
- [ ] Create `apps/ade-engine/src/ade_engine/settings.py` using `BaseSettings` with `env_prefix="ADE_ENGINE_"`, `env_file=".env"`, and custom source injecting `ade_engine.toml` reader (see `docs/settings.md`).
- [ ] Define fields: `config_package="ade_config"`, `append_unmapped_columns: bool = True`, `unmapped_prefix: str = "raw_"`, `mapping_tie_resolution: Literal["leftmost", "drop_all"] = "leftmost"`, plus logging/config roots as needed.
- [ ] Implement `settings_customise_sources` ordering: init > env vars > .env > TOML > defaults.
- [ ] Add validation for enums/prefix non-empty; provide examples in docs.

Code example:
```py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADE_ENGINE_", env_file=".env", extra="ignore")
    append_unmapped_columns: bool = True
    unmapped_prefix: str = "raw_"
    mapping_tie_resolution: Literal["leftmost", "drop_all"] = "leftmost"
    @classmethod
    def settings_customise_sources(cls, init, env, dotenv, file_secret):
        return (init, env, dotenv, toml_source, file_secret)
```

Definition of done:
- [ ] Settings class covers required keys with documented precedence; loads correctly from `.env` and `ade_engine.toml` (see template `config_package_example/settings.toml`).
