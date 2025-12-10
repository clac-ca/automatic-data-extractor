from ade_engine.registry import column_detector


@column_detector(field="email", priority=1)
def detect_email(ctx):
    return {"email": 1.0}
