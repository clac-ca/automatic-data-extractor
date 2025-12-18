from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import polars as pl


def register(registry):
    registry.register_hook(on_table_transformed, hook="on_table_transformed", priority=0)

    # Examples (uncomment to enable)
    # registry.register_hook(on_table_transformed_example_1_trim_text_and_null_empty, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_2_ensure_full_name_column, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_3_backfill_full_name, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_4_parse_amount_currency, hook="on_table_transformed", priority=0)
    # registry.register_hook(on_table_transformed_example_5_drop_all_null_rows, hook="on_table_transformed", priority=0)

    # Examples (uncomment to enable)
    # --- Enrichment: normalize & enrich addresses via Google Geocoding ---
    # registry.register_hook(on_table_transformed_example_geocode_address_full_google,hook="on_table_transformed",priority=0)


def on_table_transformed(
    *,
    hook_name,  # HookName enum value for this stage
    settings,  # Engine Settings
    metadata: dict,  # Run/sheet metadata (filenames, sheet_index, etc.)
    state: dict,  # Mutable dict shared across the run
    workbook,  # None for this stage (table hooks run before output workbook exists)
    sheet,  # Source worksheet (openpyxl Worksheet)
    table: pl.DataFrame,  # Current table DF (post-transforms; pre-validation)
    write_table,  # None for this stage
    input_file_name: str | None,  # Input filename (basename) if known
    logger,  # RunLogger (structured events + text logs)
) -> pl.DataFrame | None:
    """Post-transform hook (pre-validation).

    This hook is called once per detected table *after*:

    - header/region detection
    - mapping (source headers -> canonical field names)
    - registered column transforms (value normalization)

    and *before* validators run. The DataFrame returned from this hook (if any)
    is what validation sees next.

    Use this hook for table-level adjustments that are awkward to express as
    per-field transforms, such as:

    - cross-column fixes (derive one column from others, swap/repair related values)
    - type coercion / parsing (dates, currency) to prepare for validators
    - adding missing required columns (so downstream validators can run)
    - dropping obviously-non-data rows (blank lines, repeated headers, footers)

    If you want to filter based on validation results (e.g., drop rows that have
    issues), do that in `on_table_validated` instead.

    Return a new DataFrame to replace ``table`` (or return None to keep it).
    """

    if logger:
        logger.info("Config hook: table transformed (columns=%s)", list(table.columns))

    return None


def on_table_transformed_example_1_trim_text_and_null_empty(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example: trim whitespace and convert empty strings to nulls for all text columns."""

    return table.with_columns(pl.col(pl.Utf8).str.strip_chars().replace("", None))


def on_table_transformed_example_2_ensure_full_name_column(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example: ensure a column exists before validation (useful for optional inputs)."""

    if "full_name" not in table.columns:
        return table.with_columns(pl.lit(None).cast(pl.Utf8).alias("full_name"))
    return None


def on_table_transformed_example_3_backfill_full_name(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example: backfill `full_name` from `first_name` + `last_name` when missing."""

    if {"first_name", "last_name", "full_name"}.issubset(table.columns):
        first = pl.col("first_name").cast(pl.Utf8).str.strip_chars().replace("", None)
        last = pl.col("last_name").cast(pl.Utf8).str.strip_chars().replace("", None)
        full = pl.col("full_name").cast(pl.Utf8).str.strip_chars().replace("", None)
        return table.with_columns(
            pl.when(full.is_null() & first.is_not_null() & last.is_not_null())
            .then(pl.concat_str([first, last], separator=" "))
            .otherwise(full)
            .alias("full_name")
        )
    return None


def on_table_transformed_example_4_parse_amount_currency(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Example: parse a currency-like string column into Float64."""

    if "amount" in table.columns:
        return table.with_columns(
            pl.col("amount")
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.replace_all(r"[,$]", "")
            .cast(pl.Float64, strict=False)
            .alias("amount")
        )
    return None


def on_table_transformed_example_5_drop_all_null_rows(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame:
    """Example: drop rows that are completely empty (all columns null)."""

    return table.filter(pl.any_horizontal(pl.all().is_not_null()))


def on_table_transformed_example_geocode_address_full_google(
    *,
    hook_name,
    settings,
    metadata: dict,
    state: dict,
    workbook,
    sheet,
    table: pl.DataFrame,
    write_table,
    input_file_name: str | None,
    logger,
) -> pl.DataFrame | None:
    """Purpose: Use Google Geocoding to canonicalize `address_full` and populate address parts.

    What this teaches:
    - Detect whether a canonical column exists (`address_full`)
    - Dedupe values (“batching”) + cache results in `state` (efficient + simple)
    - Join results back and update/add columns with Polars

    Notes:
    - Google Geocoding is request-per-address (no true batch endpoint). Here “batched” means:
      dedupe + cache + one pass over unique addresses.
    - Requires a Google API key (billing/quota applies).
    """

    # 1) Only run when the column exists.
    if "address_full" not in table.columns:
        return None

    # 2) Get API key (settings first, env fallback).
    api_key = getattr(settings, "google_geocoding_api_key", None) or os.getenv("GOOGLE_GEOCODING_API_KEY")
    if not api_key:
        if logger:
            logger.warning(
                "Geocoding skipped: set settings.google_geocoding_api_key or env GOOGLE_GEOCODING_API_KEY"
            )
        return None

    # 3) Normalize address text into a stable key used for dedupe + joining.
    address_key = (
        pl.col("address_full")
        .cast(pl.Utf8)
        .str.strip_chars()
        .str.replace_all(r"\s+", " ")
    )
    address_key = pl.when(address_key.is_null() | (address_key == "")).then(pl.lit(None)).otherwise(address_key)

    unique_addresses: list[str] = (
        table.select(address_key.alias("__address_key"))
        .filter(pl.col("__address_key").is_not_null())
        .unique()
        .get_column("__address_key")
        .to_list()
    )
    if not unique_addresses:
        return None

    # 4) Cache across the whole run (prevents repeated API calls across sheets).
    #    cache[address] = {"formatted_address": ..., "city": ..., ...}
    cache: dict[str, dict] = state.setdefault("google_geocoding_cache", {})

    # 5) Geocode only addresses we haven't seen before.
    for addr in unique_addresses:
        if addr in cache:
            continue

        url = "https://maps.googleapis.com/maps/api/geocode/json?" + urlencode(
            {"address": addr, "key": api_key}
        )

        try:
            req = Request(url, headers={"User-Agent": "ade-config-template"})
            with urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if logger:
                logger.warning("Geocoding request failed for %r: %s", addr, e)
            cache[addr] = {}
            continue

        if payload.get("status") != "OK" or not payload.get("results"):
            cache[addr] = {}
            continue

        result = payload["results"][0]
        components = result.get("address_components") or []

        # Build a quick lookup by component type.
        by_type: dict[str, dict] = {}
        for comp in components:
            for t in comp.get("types", []):
                by_type.setdefault(t, comp)

        city_comp = by_type.get("locality") or by_type.get("postal_town")
        region_comp = by_type.get("administrative_area_level_1")  # state/province
        postal_comp = by_type.get("postal_code")
        country_comp = by_type.get("country")

        cache[addr] = {
            "formatted_address": result.get("formatted_address"),
            "city": city_comp.get("long_name") if city_comp else None,
            "province_state": (region_comp.get("short_name") or region_comp.get("long_name")) if region_comp else None,
            "postal_code": postal_comp.get("long_name") if postal_comp else None,
            "country": country_comp.get("long_name") if country_comp else None,
        }

    # 6) Turn cached results into a small DataFrame we can join back.
    mapping_df = pl.DataFrame(
        [
            {
                "__address_key": addr,
                "__geo_formatted_address": cache.get(addr, {}).get("formatted_address"),
                "__geo_city": cache.get(addr, {}).get("city"),
                "__geo_province_state": cache.get(addr, {}).get("province_state"),
                "__geo_postal_code": cache.get(addr, {}).get("postal_code"),
                "__geo_country": cache.get(addr, {}).get("country"),
            }
            for addr in unique_addresses
        ]
    )

    out = (
        table
        .with_columns(address_key.alias("__address_key"))
        .join(mapping_df, on="__address_key", how="left")
    )

    # 7) Update address_full to Google's canonical formatted version when present.
    formatted = pl.col("__geo_formatted_address").cast(pl.Utf8).str.strip_chars()
    formatted = pl.when(formatted.is_null() | (formatted == "")).then(pl.lit(None)).otherwise(formatted)

    original = pl.col("address_full").cast(pl.Utf8).str.strip_chars()
    original = pl.when(original.is_null() | (original == "")).then(pl.lit(None)).otherwise(original)

    out = out.with_columns(pl.coalesce([formatted, original]).alias("address_full"))

    # 8) Create / fill derived columns from geocoding results.
    #    (If the column already exists, keep it when geocoding didn’t return a value.)
    geo_city = pl.col("__geo_city").cast(pl.Utf8).str.strip_chars()
    geo_region = pl.col("__geo_province_state").cast(pl.Utf8).str.strip_chars()
    geo_postal = pl.col("__geo_postal_code").cast(pl.Utf8).str.strip_chars()
    geo_country = pl.col("__geo_country").cast(pl.Utf8).str.strip_chars()

    if "city" in out.columns:
        existing = pl.col("city").cast(pl.Utf8).str.strip_chars()
        out = out.with_columns(pl.coalesce([geo_city, existing]).alias("city"))
    else:
        out = out.with_columns(geo_city.alias("city"))

    if "province_state" in out.columns:
        existing = pl.col("province_state").cast(pl.Utf8).str.strip_chars()
        out = out.with_columns(pl.coalesce([geo_region, existing]).alias("province_state"))
    else:
        out = out.with_columns(geo_region.alias("province_state"))

    if "postal_code" in out.columns:
        existing = pl.col("postal_code").cast(pl.Utf8).str.strip_chars()
        out = out.with_columns(pl.coalesce([geo_postal, existing]).alias("postal_code"))
    else:
        out = out.with_columns(geo_postal.alias("postal_code"))

    if "country" in out.columns:
        existing = pl.col("country").cast(pl.Utf8).str.strip_chars()
        out = out.with_columns(pl.coalesce([geo_country, existing]).alias("country"))
    else:
        out = out.with_columns(geo_country.alias("country"))

    # 9) Clean up internal columns.
    out = out.drop(
        [
            "__address_key",
            "__geo_formatted_address",
            "__geo_city",
            "__geo_province_state",
            "__geo_postal_code",
            "__geo_country",
        ]
    )

    return out