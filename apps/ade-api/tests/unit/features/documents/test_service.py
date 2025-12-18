from __future__ import annotations

from pathlib import Path

import openpyxl

from ade_api.features.documents.service import DocumentsService


def test_inspect_workbook_handles_extensionless_files(tmp_path: Path) -> None:
    workbook_path = tmp_path / "workbook"

    workbook = openpyxl.Workbook()
    workbook.active.title = "Data"
    workbook.create_sheet("Extra")
    workbook.save(workbook_path)
    workbook.close()

    sheets = DocumentsService._inspect_workbook(workbook_path)

    assert [(sheet.name, sheet.index, sheet.kind, sheet.is_active) for sheet in sheets] == [
        ("Data", 0, "worksheet", True),
        ("Extra", 1, "worksheet", False),
    ]
