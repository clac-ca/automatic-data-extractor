"""Pipeline stage helpers for the ADE engine."""

from .extract import extract_inputs
from .io import list_input_files, read_table, sheet_name
from .mapping import (
    build_unmapped_header,
    column_sample,
    map_columns,
    match_header,
    normalize_header,
)
from .models import ColumnMapping, ColumnModule, ExtraColumn, FileExtraction, ScoreContribution
from .normalize import normalize_rows
from .processing import TableProcessingResult, process_table
from .output import output_headers, write_outputs
from .registry import ColumnRegistry, ColumnRegistryError

__all__ = [
    "ColumnMapping",
    "ColumnModule",
    "ColumnRegistry",
    "ColumnRegistryError",
    "ExtraColumn",
    "FileExtraction",
    "ScoreContribution",
    "TableProcessingResult",
    "build_unmapped_header",
    "column_sample",
    "extract_inputs",
    "list_input_files",
    "map_columns",
    "match_header",
    "normalize_header",
    "normalize_rows",
    "process_table",
    "output_headers",
    "read_table",
    "sheet_name",
    "write_outputs",
]
