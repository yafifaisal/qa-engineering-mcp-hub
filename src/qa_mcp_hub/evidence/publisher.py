"""Publish evidence only after an explicit review and a single-use approval.

Purpose: preview publication and send at most one external request.
Milestone: 10
Status: IMPLEMENTED
Ownership: evidence.publisher
Dependencies: Approvals, execution store, and the one-shot HTTP client.
Expected tests: denied publication, one POST, and no automatic retry.
"""

import re
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from qa_mcp_hub.adapters.cicd.base import post_once
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.core.approvals import ApprovalLedger
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.core.models import ProviderKind
from qa_mcp_hub.evidence.manifest import manifest_digest
from qa_mcp_hub.evidence.models import (
    EvidenceManifest,
    EvidencePolicy,
    PublicationPreview,
    ReviewState,
)
from qa_mcp_hub.storage.execution_store import ExecutionStore
from qa_mcp_hub.workflows.models import ExecutionRecord

_DESTINATIONS = frozenset({"local", "jira", "xray", "testrail"})
_PROVIDERS = {
    "jira": ProviderKind.jira,
    "xray": ProviderKind.xray,
    "testrail": ProviderKind.testrail,
}
_session_factory: Callable[[], tuple[httpx.Client, str]] | None = None


def install_publication_session(
    factory: Callable[[], tuple[httpx.Client, str]],
) -> None:
    """Install a test HTTP client. Production calls use the same guard."""
    global _session_factory
    _session_factory = factory


def clear_publication_session() -> None:
    """Remove a test HTTP client."""
    global _session_factory
    _session_factory = None


def prepare_publication(
    manifest: EvidenceManifest, destination: str
) -> PublicationPreview:
    """Describe publication. This function does not call a provider."""
    if destination not in _DESTINATIONS:
        reason = "publication_rejected"
    else:
        reason = "approval_required"
    return PublicationPreview(
        executed=False,
        reason=reason,
        execution_id=manifest.execution_id,
        destination=destination,
        review_state=manifest.review_state,
    )


def publish_manifest(
    *,
    manifest: EvidenceManifest,
    policy: EvidencePolicy,
    record: ExecutionRecord,
    config: HubConfig,
    profile_id: str,
    store: ExecutionStore,
    ledger: ApprovalLedger,
    destination: str,
    token: str,
    confirmed: bool,
    qa_review: str,
    now: datetime,
    issue_key: str = "",
) -> PublicationPreview:
    """Publish once. A repeated digest does not send another request."""
    if qa_review != "APPROVED":
        return _preview(manifest, destination, "publication_rejected")
    if destination not in _DESTINATIONS:
        return _preview(manifest, destination, "publication_rejected")
    if not confirmed or not _mutations(config, profile_id):
        return _preview(manifest, destination, "publication_disabled")
    if destination != "local" and policy.external_publication != "approval_required":
        return _preview(manifest, destination, "publication_disabled")
    digest = manifest_digest(manifest)
    existing = store.publication_state(digest)
    if existing is not None:
        reason = (
            "already_published" if existing == "published" else "publication_incomplete"
        )
        return _preview(manifest, destination, reason)
    if destination != "local":
        _target(destination, config, profile_id, record, issue_key)
    ledger.consume(
        token,
        job_id=manifest.execution_id,
        parameter_digest=digest,
        now=now,
        expected_action="evidence_publication",
    )
    store.set_review_state(profile_id, manifest.execution_id, "APPROVED")
    store.record_publication(
        digest=digest,
        execution_id=manifest.execution_id,
        profile_id=profile_id,
        state="started",
    )
    if destination != "local":
        _post(destination, config, profile_id, record, manifest, digest, issue_key)
    store.record_publication(
        digest=digest,
        execution_id=manifest.execution_id,
        profile_id=profile_id,
        state="published",
    )
    return PublicationPreview(
        executed=True,
        reason="published",
        execution_id=manifest.execution_id,
        destination=destination,
        review_state=ReviewState.approved,
    )


def _post(
    destination: str,
    config: HubConfig,
    profile_id: str,
    record: ExecutionRecord,
    manifest: EvidenceManifest,
    digest: str,
    issue_key: str,
) -> None:
    if _session_factory is None:
        raise HubError(
            "credential_missing", "evidence publication credential is missing"
        )
    url, host = _target(destination, config, profile_id, record, issue_key)
    client, token = _session_factory()
    try:
        post_once(
            client,
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            body={
                "execution_id": manifest.execution_id,
                "manifest_digest": digest,
                "overall": manifest.overall.value,
            },
            allowed_host=host,
        )
    finally:
        client.close()


def _target(
    destination: str,
    config: HubConfig,
    profile_id: str,
    record: ExecutionRecord,
    issue_key: str,
) -> tuple[str, str]:
    provider = _PROVIDERS[destination]
    connection = next(
        (
            item
            for item in config.connections
            if item.id in config.profiles[profile_id].connection_ids
            and item.enabled
            and item.provider is provider
            and item.base_url
        ),
        None,
    )
    if destination == "xray":
        if connection is None:
            raise HubError(
                "publication_rejected", "publication connection is not approved"
            )
        return (
            "https://xray.cloud.getxray.app/api/v2/import/execution",
            "xray.cloud.getxray.app",
        )
    if connection is None or connection.base_url is None:
        raise HubError("publication_rejected", "publication connection is not approved")
    host = urlsplit(connection.base_url).hostname
    if host is None:
        raise HubError("connection_invalid", "provider host is missing")
    base = connection.base_url.rstrip("/")
    if destination == "jira":
        if issue_key not in _issue_keys(record):
            raise HubError("publication_rejected", "issue key was not part of the run")
        return f"{base}/rest/api/3/issue/{issue_key}/attachments", host
    return f"{base}/index.php?/api/v2/add_results", host


def _issue_keys(record: ExecutionRecord) -> set[str]:
    text = " ".join(step.target for step in record.step_results)
    text = f"{text} {record.excerpt}"
    return set(re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", text))


def _mutations(config: HubConfig, profile_id: str) -> bool:
    override = config.profiles[profile_id].execution.allow_mutations
    if override is not None:
        return override
    return config.execution.allow_mutations


def _preview(
    manifest: EvidenceManifest, destination: str, reason: str
) -> PublicationPreview:
    return PublicationPreview(
        executed=False,
        reason=reason,
        execution_id=manifest.execution_id,
        destination=destination,
        review_state=manifest.review_state,
    )
