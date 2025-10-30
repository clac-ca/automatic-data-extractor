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

## Quick start: add a SIN field (detect → transform → validate)

Goal: teach ADE to recognize a SIN column, normalize values, and flag invalid ones.

1. **Add `columns/sin.py`**

```python
# columns/sin.py
import re

_DIGITS = re.compile(r"\d+")
def _only_digits(s): return "".join(_DIGITS.findall(str(s))) if s is not None else ""
def _luhn_ok(d):
    if len(d) != 9 or not d.isdigit(): return False
    total = 0
    for i, ch in enumerate(d):
        n = ord(ch) - 48
        if (i + 1) % 2 == 0:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0

# --- Pass 2: detection ---------------------------------------------------------
def detect_synonyms(*, header: str | None, field_name: str, field_meta: dict, **_):
    score = 0.0
    if header:
        h = header.lower()
        for syn in field_meta.get("synonyms", []):
            if syn.lower() in h:
                score += 0.6
    return {"scores": {field_name: round(score, 2)}}

def detect_value_shape(*, values_sample: list, field_name: str, **_):
    if not values_sample: return {"scores": {field_name: 0.0}}
    total = valid = 0
    for v in values_sample:
        if v in (None, ""): continue
        total += 1
        d = _only_digits(v)
        if len(d) == 9 and _luhn_ok(d): valid += 1
    if total == 0: return {"scores": {field_name: 0.0}}
    ratio = valid / total
    return {"scores": {field_name: 0.9 if ratio >= 0.8 else round(0.5 * ratio, 2)}}

# --- Pass 3: transform (optional) ---------------------------------------------
def transform(*, values: list, **_):
    def fmt(d): return f"{d[:3]}-{d[3:6]}-{d[6:]}"
    out, normalized = [], 0
    for v in values:
        if v in (None, ""): out.append(None); continue
        d = _only_digits(v)
        if len(d) == 9: out.append(fmt(d)); normalized += 1
        else: out.append(v)
    return {"values": out, "warnings": [f"normalized: {normalized}/{len(values)}"]}

# --- Pass 4: validate (optional) ----------------------------------------------
def validate(*, values: list, field_meta: dict, **_):
    issues, required = [], bool(field_meta.get("required"))
    for i, v in enumerate(values, start=1):
        d = _only_digits(v)
        blankish = (v is None) or (str(v).strip() == "")
        if required and blankish:
            issues.append({"row_index": i, "code": "required_missing",
                           "severity": "error", "message": "SIN is required."})
        elif not blankish and (len(d) != 9 or not _luhn_ok(d)):
            issues.append({"row_index": i, "code": "sin_invalid",
                           "severity": "error", "message": "Invalid SIN."})
    return {"issues": issues}
```

2. **Add it to `manifest.json`**

```json
{
  "columns": {
    "order": ["sin", "first_name", "department"],
    "meta": {
      "sin": {
        "label": "SIN",
        "required": true,
        "script": "columns/sin.py",
        "synonyms": ["sin", "social insurance number", "sin number", "social-insurance-number"]
      }
    }
  }
}
```

3. **Run a job from the UI**  
Activate the config if needed, upload a workbook, and run the job. ADE streams rows, applies your rules, and writes `normalized.xlsx`.

4. **Inspect the artifact (`artifact.json`)**  
Confirm mapping scores, see transform warnings, and review validation issues with A1 locations. Full artifact reference: [14-Job Artifact JSON](./14-job_artifact_json.md).

## Notes
Normalize case and whitespace early inside transforms. Prefer explicit parsing and error handling for numeric fields.

## What to read next
Jump to [11-troubleshooting.md](./11-troubleshooting.md) for common failure modes and fixes.

---

Previous: [07-pass-generate-normalized-workbook.md](./07-pass-generate-normalized-workbook.md)  
Next: [11-troubleshooting.md](./11-troubleshooting.md)
