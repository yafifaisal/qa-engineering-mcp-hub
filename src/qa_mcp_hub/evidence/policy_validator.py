"""Validate an evidence policy before it can collect a run.

Purpose: reject overlapping checks and unknown completeness results.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.policy_validator
Dependencies: Evidence policy model.
Expected tests: overlap, unknown check, and missing-result values.
"""

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.models import EvidencePolicy

_CHECKS = frozenset({"api", "database", "kafka", "business", "security_redaction"})
_MISSING = frozenset({"FAILED", "INCONCLUSIVE", "NOT_EXECUTED"})
_PROFILES = frozenset({"standard", "strict"})
_PUBLICATION = frozenset({"deny", "approval_required"})


def validate_policy(policy: EvidencePolicy) -> EvidencePolicy:
    """Reject a policy that could hide a missing mandatory check."""
    required = set(policy.required_checks)
    optional = set(policy.optional_checks)
    if not required:
        raise HubError("mapping_rejected", "evidence policy has no required checks")
    if not required <= _CHECKS or not optional <= _CHECKS:
        raise HubError("mapping_rejected", "evidence policy check is not recognized")
    if required & optional:
        raise HubError("mapping_rejected", "evidence policy repeats a check")
    if policy.missing_required_result not in _MISSING:
        raise HubError("mapping_rejected", "missing evidence result is not recognized")
    if policy.redaction.profile not in _PROFILES:
        raise HubError("mapping_rejected", "redaction profile is not recognized")
    if policy.external_publication not in _PUBLICATION:
        raise HubError("mapping_rejected", "publication mode is not recognized")
    if "security_redaction" not in required:
        raise HubError("mapping_rejected", "security redaction is mandatory")
    return policy
