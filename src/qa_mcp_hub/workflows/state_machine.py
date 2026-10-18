"""Legal execution status transitions.

Purpose: keep terminal runs immutable and the path explicit.
Milestone: 06
Status: IMPLEMENTED
Ownership: workflows.state_machine
Dependencies: Execution status.
Expected tests: legal transitions and terminal immutability.
"""

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.workflows.models import ExecutionStatus

_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.queued: frozenset(
        {ExecutionStatus.running, ExecutionStatus.cancelled}
    ),
    ExecutionStatus.running: frozenset(
        {
            ExecutionStatus.verifying,
            ExecutionStatus.timed_out,
            ExecutionStatus.cancelled,
            ExecutionStatus.error,
        }
    ),
    ExecutionStatus.verifying: frozenset(
        {
            ExecutionStatus.passed,
            ExecutionStatus.failed,
            ExecutionStatus.inconclusive,
            ExecutionStatus.error,
            ExecutionStatus.blocked,
        }
    ),
}
_TERMINAL = frozenset(
    {
        ExecutionStatus.passed,
        ExecutionStatus.failed,
        ExecutionStatus.blocked,
        ExecutionStatus.inconclusive,
        ExecutionStatus.cancelled,
        ExecutionStatus.timed_out,
        ExecutionStatus.error,
    }
)


def transition(current: ExecutionStatus, nxt: ExecutionStatus) -> ExecutionStatus:
    """Move to the next status or reject an illegal change."""
    if current in _TERMINAL:
        raise HubError("terminal_state", f"{current.value} cannot change")
    allowed = _TRANSITIONS.get(current, frozenset())
    if nxt not in allowed:
        raise HubError(
            "illegal_transition",
            f"{current.value} cannot become {nxt.value}",
        )
    return nxt


def is_terminal(status: ExecutionStatus) -> bool:
    """Return whether a status can no longer change."""
    return status in _TERMINAL
