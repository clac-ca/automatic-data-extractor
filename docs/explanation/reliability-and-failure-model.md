# Reliability and Failure Model

## Purpose

Explain how ADE avoids lost work and handles failures.

## Key Ideas

- A run is claimed by one worker at a time.
- Claims have a lease timeout.
- Workers renew leases while processing.
- Failed runs can retry until `max_attempts` is reached.

## What Happens If a Worker Dies

- Lease renewal stops.
- Lease expires.
- System requeues or fails the run based on retry rules.

## Retry Behavior

- If attempts remain, run returns to `queued` with delayed retry.
- Delay grows over attempts (exponential backoff).
- When attempts are exhausted, run becomes `failed`.

## Environment Build Reliability

- Worker builds reusable execution environments.
- Environment builds are locked to avoid duplicate concurrent builds.
- Failed environment builds are recorded and surfaced in logs/events.

## Why This Helps

- one failing run does not stop whole worker service
- retries handle transient failures
- terminal failures keep clear error history for triage
