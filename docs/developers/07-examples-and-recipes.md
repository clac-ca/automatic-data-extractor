# Examples & Recipes

Short, copy‑pasteable patterns you can adapt in column modules. Keep examples under 30 lines, prefer realistic values, and add warnings where helpful. Review `01-config-packages.md` for detector and transform contracts.

## Member ID

```python
# columns/member_id.py
def detect_header(*, header: str, samples: list[str], **_):
    score = 1.0 if 'member' in header.lower() and 'id' in header.lower() else 0.0
    return {"score": score}

def transform(*, column: list[str], **_):
    return {"values": [v.strip().upper() for v in column], "warnings": []}
```

## First/Last names (split)

```python
# columns/first_name.py
def detect_header(*, header: str, **_):
    return {"score": 1.0 if 'first' in header.lower() else 0.0}

def transform(*, column: list[str], **_):
    return {"values": [v.split()[0] if v else '' for v in column], "warnings": []}
```

## Currency total

```python
# columns/invoice_total.py
def detect_header(*, header: str, **_):
    return {"score": 1.0 if 'total' in header.lower() else 0.0}

def transform(*, column: list[str], **_):
    values, warnings = [], []
    for i, v in enumerate(column):
        try:
            values.append(float(str(v).replace(',', '').replace('$', '')))
        except Exception:
            values.append(None)
            warnings.append({"row": i, "code": "non_numeric", "value": v})
    return {"values": values, "warnings": warnings}
```

## Notes
Normalize case and whitespace early inside transforms. Prefer explicit parsing and error handling for numeric fields.

## What to read next
Read `08-scaling-and-performance.md` for guidance on throughput and memory.
