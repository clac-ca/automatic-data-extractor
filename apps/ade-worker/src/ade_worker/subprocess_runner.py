"""Run subprocesses and capture NDJSON logs.

The worker's contract with the engine is:
- run `ade_engine` with `--log-format ndjson`
- stream every line into an on-disk NDJSON log
- parse JSON lines so we can extract `engine.run.completed` payload
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


class EventLog:
    """Append-only NDJSON log file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")

    def emit(self, *, event: str, level: str = "info", message: str = "", data: dict[str, Any] | None = None, context: dict[str, Any] | None = None) -> None:
        rec: dict[str, Any] = {
            "timestamp": utc_iso(),
            "level": level,
            "event": event,
            "message": message,
            "data": data or {},
        }
        if context:
            rec["context"] = dict(context)
        self.append(rec)


@dataclass(frozen=True, slots=True)
class SubprocessResult:
    exit_code: int
    timed_out: bool
    duration_seconds: float


class SubprocessRunner:
    def run(
        self,
        cmd: list[str],
        *,
        event_log: EventLog,
        scope: str,
        timeout_seconds: float | None,
        cwd: str | None,
        env: dict[str, str] | None,
        heartbeat: Callable[[], None] | None = None,
        heartbeat_interval: float = 15.0,
        context: dict[str, Any] | None = None,
        on_json_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> SubprocessResult:
        start = time.monotonic()
        deadline = (start + float(timeout_seconds)) if timeout_seconds is not None else None

        event_log.emit(event=f"{scope}.start", message="Starting subprocess", data={"cmd": cmd, "cwd": cwd or ""}, context=context)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=env,
            start_new_session=(os.name != "nt"),
        )

        errors: list[BaseException] = []
        timed_out = False

        def drain(stream, stream_name: str) -> None:
            try:
                assert stream is not None
                for raw in iter(stream.readline, ""):
                    line = raw.rstrip("\n")
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        obj = None

                    if isinstance(obj, dict) and "event" in obj:
                        # Preserve engine events as-is, but attach context for correlation.
                        if context:
                            obj = dict(obj)
                            obj.setdefault("context", {})
                            if isinstance(obj["context"], dict):
                                obj["context"].update(dict(context))
                            else:
                                obj["context"] = dict(context)
                        event_log.append(obj)
                        if on_json_event:
                            on_json_event(obj)
                    else:
                        event_log.emit(event=f"{scope}.{stream_name}", message=line, context=context)
            except BaseException as exc:
                errors.append(exc)
            finally:
                try:
                    stream.close()  # type: ignore[attr-defined]
                except Exception:
                    pass

        threads = [
            threading.Thread(target=drain, args=(proc.stdout, "stdout"), daemon=True),
            threading.Thread(target=drain, args=(proc.stderr, "stderr"), daemon=True),
        ]
        for t in threads:
            t.start()

        last_hb = 0.0
        if heartbeat:
            heartbeat()
            last_hb = time.monotonic()

        while True:
            if errors:
                raise errors[0]

            now = time.monotonic()

            if heartbeat and (now - last_hb) >= float(heartbeat_interval):
                heartbeat()
                last_hb = now

            if deadline is not None and now >= deadline:
                timed_out = True
                self._terminate(proc)
                break

            rc = proc.poll()
            if rc is not None:
                break

            time.sleep(0.05)

        # Reap the process.
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._terminate(proc)

        for t in threads:
            t.join(timeout=2)

        if errors:
            raise errors[0]

        duration = max(0.0, time.monotonic() - start)
        exit_code = int(proc.returncode or 0)
        if timed_out:
            # Conventional timeout exit code.
            exit_code = 124

        event_log.emit(
            event=f"{scope}.complete",
            message="Subprocess finished",
            data={"cmd": cmd, "exit_code": exit_code, "timed_out": timed_out, "duration_seconds": duration},
            context=context,
        )

        return SubprocessResult(exit_code=exit_code, timed_out=timed_out, duration_seconds=duration)

    def _terminate(self, proc: subprocess.Popen) -> None:
        try:
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return
            else:
                proc.terminate()
        except Exception:
            pass

        try:
            proc.wait(timeout=5)
            return
        except Exception:
            pass

        try:
            if os.name != "nt":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass


__all__ = ["EventLog", "SubprocessRunner", "SubprocessResult"]
