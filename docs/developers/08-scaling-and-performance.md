# Scaling & Performance

Scale by controlling what you hold in memory. Use small samples to decide during detection, then process full columns efficiently during transform. Add chunking only when files are huge. If you must spill, do it deliberately and document the trade‑offs.

## Sampling policy
Detectors operate on small samples. Size is tunable via manifest (`detect.sample`).

## Two‑phase execution
Detection (samples) → Transform (full columns). Keeps memory flat and logic explainable.

## Column‑wise transforms
Operate on vectors of values; optionally chunk when huge. Chunking can be added without changing contracts.

## Spill strategy
Only as a last resort; document trade‑offs (throughput vs. simplicity) before adopting.

## What to read next
Read `09-security-and-secrets.md` for guidance on handling secrets safely.
