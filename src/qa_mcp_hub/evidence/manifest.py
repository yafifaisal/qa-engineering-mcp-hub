"""Bind an evidence manifest to one stored execution.

Purpose: hash report bytes and reject a manifest for a different execution.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.manifest
Dependencies: Evidence models and hashing.
Expected tests: digest stability and tamper detection.
"""

import hashlib
import json

from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.evidence.models import EvidenceArtifact, EvidenceManifest


def digest_bytes(content: bytes) -> str:
    """Return the SHA-256 hex digest of artifact bytes."""
    return hashlib.sha256(content).hexdigest()


def artifact_for(name: str, content: bytes) -> EvidenceArtifact:
    """Describe one artifact without writing it."""
    return EvidenceArtifact(name=name, sha256=digest_bytes(content), size=len(content))


def manifest_digest(manifest: EvidenceManifest) -> str:
    """Hash the execution id and artifact digests. Review state is excluded."""
    payload = {
        "execution_id": manifest.execution_id,
        "artifacts": [
            {"name": item.name, "sha256": item.sha256} for item in manifest.artifacts
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return digest_bytes(encoded)


def require_same_execution(manifest: EvidenceManifest, execution_id: str) -> None:
    """Refuse a manifest that was loaded for a different run."""
    if manifest.execution_id != execution_id:
        raise HubError("unknown_execution", "evidence manifest does not match the run")


def verify_artifact(content: bytes, expected: EvidenceArtifact) -> None:
    """Reject bytes whose digest or size differs from the manifest."""
    if digest_bytes(content) != expected.sha256 or len(content) != expected.size:
        raise HubError("artifact_rejected", "evidence artifact digest does not match")
