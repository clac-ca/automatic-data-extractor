"""Row detectors used to classify header vs data rows.

Each `detect_*` function in this package returns either a float for its label
or a dict of label deltas. The engine sums scores from all detectors.
"""

__all__ = []
