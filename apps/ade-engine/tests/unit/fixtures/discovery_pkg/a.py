from ade_engine.registry import row_detector, RowKind


@row_detector(row_kind=RowKind.HEADER, priority=5)
def detect_header(ctx):
    return 1.0
