"""Row detectors used to classify header vs data rows.

Each `detect_*` function in this package returns either a float for its default
label (set via ``DEFAULT_LABEL`` in the module) or a dict of label deltas. The
engine sums scores from all detectors.
"""

__all__ = []
