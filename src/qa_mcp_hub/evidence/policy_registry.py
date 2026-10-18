"""Load versioned evidence policies from the QA workspace.

Purpose: read the reviewed policy files and reject an unknown policy id.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.policy_registry
Dependencies: Path allowlist and evidence models.
Expected tests: the four workspace policies and a missing policy.
"""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.models import EvidencePolicy
from qa_mcp_hub.security.path_allowlist import resolve_within

_LIMIT = 65536


def load_policies(workspace: Path) -> dict[str, EvidencePolicy]:
    """Load every policy YAML file under the workspace evidence directory."""
    root = workspace / "evidence-policies"
    if not root.is_dir():
        return {}
    found: dict[str, EvidencePolicy] = {}
    for path in sorted(root.glob("*.yaml")):
        resolved = resolve_within(path, [workspace])
        if resolved.stat().st_size > _LIMIT:
            raise HubError("mapping_invalid", "evidence policy file is too large")
        loaded = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise HubError("mapping_invalid", "evidence policy file is not a mapping")
        try:
            policy = EvidencePolicy.model_validate(loaded)
        except ValidationError as exc:
            raise HubError(
                "mapping_invalid", "evidence policy file is invalid"
            ) from exc
        if policy.id in found:
            raise HubError("duplicate_case", "evidence policy id is duplicated")
        found[policy.id] = policy
    return found


def require_policy(
    policies: dict[str, EvidencePolicy], policy_id: str
) -> EvidencePolicy:
    """Return one implemented policy."""
    policy = policies.get(policy_id)
    if policy is None:
        raise HubError(
            "mapping_not_registered", "evidence policy is not in the workspace"
        )
    if policy.implementation_status != "IMPLEMENTED":
        raise HubError("mapping_rejected", "evidence policy is not implemented")
    return policy
