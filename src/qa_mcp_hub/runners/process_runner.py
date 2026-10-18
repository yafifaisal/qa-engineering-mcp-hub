"""Bounded execution of a registry-owned argument list.

Purpose: run one approved command without shell interpolation.
Milestone: 06
Status: IMPLEMENTED
Ownership: runners.process_runner
Dependencies: Process policy and redaction.
Expected tests: timeouts, cancellation, output bounds, and redaction.
"""

import subprocess
import threading
import time
from dataclasses import dataclass

from qa_mcp_hub.auth.redaction import redact_text
from qa_mcp_hub.security.process_policy import output_limit, stored_output_limit


@dataclass(frozen=True)
class ProcessRequest:
    """One argv vector. There is no shell flag on this request."""

    argv: tuple[str, ...]
    cwd: str
    env: dict[str, str]
    timeout_seconds: int
    secrets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcessResult:
    """Captured process facts after redaction and truncation."""

    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    cancelled: bool
    truncated: bool


def run_process(
    request: ProcessRequest, cancel: threading.Event | None = None
) -> ProcessResult:
    """Run argv with shell disabled. Cancellation and timeout stop the child."""
    if cancel is not None and cancel.is_set():
        return ProcessResult(None, "", "", False, True, False)
    process = subprocess.Popen(  # noqa: S603 - registry-built argument list
        list(request.argv),
        cwd=request.cwd,
        env=request.env,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout_box: list[str] = [""]
    stderr_box: list[str] = [""]
    overflow = threading.Event()
    readers = (
        threading.Thread(
            target=_drain,
            args=(process.stdout, stdout_box, overflow),
        ),
        threading.Thread(
            target=_drain,
            args=(process.stderr, stderr_box, overflow),
        ),
    )
    for reader in readers:
        reader.start()
    timed_out, cancelled = _wait(process, request.timeout_seconds, cancel, overflow)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)
    for reader in readers:
        reader.join(timeout=2)
    stdout, stderr, truncated = _redact(stdout_box[0], stderr_box[0], request.secrets)
    return ProcessResult(
        process.returncode,
        stdout,
        stderr,
        timed_out,
        cancelled,
        truncated or overflow.is_set(),
    )


def _drain(pipe: object, box: list[str], overflow: threading.Event) -> None:
    chunks: list[str] = []
    total = 0
    reader = getattr(pipe, "read", None)
    if reader is None:
        return
    while True:
        piece = reader(4096)
        if not isinstance(piece, str) or piece == "":
            break
        total += len(piece)
        if total > output_limit():
            overflow.set()
            break
        chunks.append(piece)
    box[0] = "".join(chunks)


def _wait(
    process: subprocess.Popen[str],
    timeout_seconds: int,
    cancel: threading.Event | None,
    overflow: threading.Event,
) -> tuple[bool, bool]:
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None:
        if cancel is not None and cancel.is_set():
            process.terminate()
            return False, True
        if overflow.is_set() or time.monotonic() >= deadline:
            process.kill()
            return not overflow.is_set(), False
        time.sleep(0.02)
    return False, False


def _redact(
    stdout: str, stderr: str, secrets: tuple[str, ...]
) -> tuple[str, str, bool]:
    limit = stored_output_limit()
    redacted_out = redact_text(stdout, secrets=secrets)
    redacted_err = redact_text(stderr, secrets=secrets)
    truncated = len(redacted_out) > limit or len(redacted_err) > limit
    return redacted_out[:limit], redacted_err[:limit], truncated
