"""Deny-by-default decisions for provider calls and repository indexing.

Purpose: record whether an operation may be planned without executing it.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.policies
Dependencies: Core context, approvals, audit, and security policy modules.
Expected tests: default denial, scoped grants, precedence, and stable decisions.
"""

from pydantic import BaseModel, ConfigDict

from qa_mcp_hub.core.enums import IndexingPermission


class PolicyDecision(BaseModel):
    """A stable authorization result. Execution waits for a later milestone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    permitted: bool
    execute: bool
    reason: str


def authorize_provider_operation(*, mutating: bool) -> PolicyDecision:
    """Refuse every provider operation. No adapter is executable in this milestone."""
    if mutating:
        reason = "mutation_not_approved"
    else:
        reason = "provider_operation_not_implemented"
    return PolicyDecision(permitted=False, execute=False, reason=reason)


def authorize_indexing(permission: IndexingPermission) -> PolicyDecision:
    """Honor an explicit indexing grant only as permission to plan, not to index."""
    if permission is IndexingPermission.none:
        return PolicyDecision(
            permitted=False,
            execute=False,
            reason="indexing_not_permitted",
        )
    return PolicyDecision(
        permitted=True,
        execute=False,
        reason="registration_only_until_milestone_05",
    )
