"""MCP tools for canonical test-case import and comparison.

Purpose: search and preview cases without publishing results.
Milestone: 09
Status: IMPLEMENTED
Ownership: mcp.tools.test_management
Dependencies: Test-management adapters, mappings, and approvals.
Expected tests: mapping, roundtrip, formula safety, and disabled publication.
"""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from qa_mcp_hub.adapters.cicd.base import post_once
from qa_mcp_hub.adapters.git.base import ReadOnlyClient
from qa_mcp_hub.adapters.test_management.base import (
    CanonicalCase,
    CaseComparison,
    ExportPreview,
    FieldMapping,
    ImportPreview,
    PublicationPreview,
    compare_cases,
    content_digest,
    load_mappings,
    require_mapping,
)
from qa_mcp_hub.adapters.test_management.google_sheets import (
    cases_from_values,
    fetch_values,
)
from qa_mcp_hub.adapters.test_management.spreadsheet import (
    _csv_text,
    export_csv,
    export_xlsx,
    import_csv,
    import_xlsx,
)
from qa_mcp_hub.adapters.test_management.testrail import cases_from_payload, fetch_cases
from qa_mcp_hub.adapters.test_management.xray import (
    cases_from_cloud,
    cases_from_data_center,
    fetch_cloud,
    fetch_data_center,
)
from qa_mcp_hub.config.loader import load_config
from qa_mcp_hub.config.models import HubConfig
from qa_mcp_hub.core.approvals import ApprovalLedger
from qa_mcp_hub.core.errors import HubError
from qa_mcp_hub.core.policies import authorize_pipeline_trigger
from qa_mcp_hub.planning.coverage_mapper import NormalizedCoverage, report_test_coverage
from qa_mcp_hub.verification.service import workspace_for

_session_factory: Callable[[], tuple[httpx.Client, str, tuple[str, ...]]] | None = None
_published: set[str] = set()


def install_test_session(
    factory: Callable[[], tuple[httpx.Client, str, tuple[str, ...]]],
) -> None:
    """Install a test HTTP session. Production reads use the configured client."""
    global _session_factory
    _session_factory = factory


def clear_test_session() -> None:
    """Remove a test HTTP session."""
    global _session_factory
    _session_factory = None


def reset_publications() -> None:
    """Clear idempotency keys recorded by the guarded publication path."""
    _published.clear()


def search_test_cases_tool(
    query: str,
    mapping_id: str,
    profile: str | None = None,
) -> tuple[CanonicalCase, ...]:
    """Search canonical cases. Provider text is untrusted data."""
    cases = _cases(mapping_id, profile)
    needle = query.casefold()
    found = [
        case
        for case in cases
        if needle in case.test_case.casefold()
        or needle in case.scenario.casefold()
        or any(needle in step.casefold() for step in case.steps)
    ]
    return tuple(found[:20])


def compare_test_cases_tool(
    mapping_id: str,
    left_id: str,
    right_id: str,
    other_mapping_id: str | None = None,
    profile: str | None = None,
) -> CaseComparison:
    """Compare two cases on the shared canonical fields."""
    left = _by_id(_cases(mapping_id, profile), left_id)
    right = _by_id(_cases(other_mapping_id or mapping_id, profile), right_id)
    return compare_cases(left, right)


def preview_test_case_import_tool(
    mapping_id: str,
    profile: str | None = None,
) -> ImportPreview:
    """Preview an import. Nothing is written."""
    cases = _cases(mapping_id, profile)
    preserved = tuple(field.name for case in cases for field in case.preserved_fields)
    return ImportPreview(
        mapping_id=mapping_id,
        dry_run=True,
        written=False,
        cases=cases,
        preserved_fields=preserved,
    )


def export_test_cases_tool(
    mapping_id: str,
    destination: str,
    dry_run: bool = True,
    profile: str | None = None,
) -> ExportPreview:
    """Export canonical cases to a workspace CSV or XLSX file."""
    _profile, workspace = _workspace(profile)
    cases = _cases(mapping_id, profile)
    if dry_run:
        text, neutralized = _csv_text(cases)
        return ExportPreview(
            mapping_id=mapping_id,
            dry_run=True,
            written=False,
            path=destination,
            digest=content_digest(text),
            formula_neutralized=neutralized,
            preview_truncated=len(text) > 4000,
            reason="preview",
        )
    path = _destination(workspace, destination)
    if destination.endswith(".xlsx"):
        _text, neutralized, digest, changed = export_xlsx(cases, path, workspace)
    else:
        _text, neutralized, digest, changed = export_csv(cases, path, workspace)
    reason = "exported" if changed else "already_exported"
    return ExportPreview(
        mapping_id=mapping_id,
        dry_run=False,
        written=changed,
        path=destination,
        digest=digest,
        formula_neutralized=neutralized,
        reason=reason,
    )


def prepare_result_publication_tool(
    mapping_id: str,
    execution_id: str,
    source_ids: list[str] | None = None,
    profile: str | None = None,
) -> PublicationPreview:
    """Preview result publication. This tool does not call a provider."""
    _profile, workspace = _workspace(profile)
    mapping = require_mapping(load_mappings(workspace), mapping_id)
    ids = tuple(source_ids or ())
    if not mapping.allow_publish:
        reason = "publication_disabled"
    elif not _execution_id_ok(execution_id) or not ids:
        reason = "publication_rejected"
    else:
        reason = "approval_required"
    return PublicationPreview(
        executed=False,
        reason=reason,
        execution_id=execution_id,
        source_ids=ids,
    )


def report_suite_coverage(
    mapping_id: str,
    suite_results: dict[str, str],
    profile: str | None = None,
) -> tuple[NormalizedCoverage, ...]:
    """Correlate automation suite ids. This is not an MCP publication tool."""
    cases = _cases(mapping_id, profile)
    links = tuple((case.source_id, case.automation_suite_id) for case in cases)
    return report_test_coverage(links, suite_results)


def dispatch_result_publication(
    mapping_id: str,
    *,
    execution_id: str,
    source_ids: tuple[str, ...],
    ledger: ApprovalLedger,
    token: str,
    confirmed: bool,
    now: datetime,
    profile: str | None = None,
) -> PublicationPreview:
    """Publish once when every guard passes. This function is not an MCP tool."""
    config = load_config()
    profile_id, workspace = workspace_for(config, profile)
    mapping = require_mapping(load_mappings(workspace), mapping_id)
    if not _execution_id_ok(execution_id) or not source_ids:
        return PublicationPreview(
            executed=False,
            reason="publication_rejected",
            execution_id=execution_id,
            source_ids=source_ids,
        )
    decision = authorize_pipeline_trigger(
        allow_trigger=mapping.allow_publish,
        mutations_allowed=_mutations(config, profile_id),
        confirmed=confirmed,
        approval_valid=True,
    )
    if not decision.execute:
        reason = (
            "publication_disabled" if not mapping.allow_publish else decision.reason
        )
        return PublicationPreview(
            executed=False,
            reason=reason,
            execution_id=execution_id,
            source_ids=source_ids,
        )
    if mapping.format != "api":
        return PublicationPreview(
            executed=False,
            reason="publication_rejected",
            execution_id=execution_id,
            source_ids=source_ids,
        )
    if _session_factory is None:
        raise HubError("credential_missing", "test-management credential is missing")
    digest = content_digest(execution_id + "|" + "|".join(source_ids))
    if digest in _published:
        return PublicationPreview(
            executed=False,
            reason="already_published",
            execution_id=execution_id,
            source_ids=source_ids,
        )
    ledger.consume(token, job_id=mapping.id, parameter_digest=digest, now=now)
    _post_once(mapping, execution_id=execution_id, source_ids=source_ids, digest=digest)
    _published.add(digest)
    return PublicationPreview(
        executed=True,
        reason="published",
        execution_id=execution_id,
        source_ids=source_ids,
    )


def _cases(mapping_id: str, profile: str | None) -> tuple[CanonicalCase, ...]:
    _profile, workspace = _workspace(profile)
    mapping = require_mapping(load_mappings(workspace), mapping_id)
    if mapping.format == "csv":
        return import_csv(workspace / mapping.source, workspace, mapping)
    if mapping.format == "xlsx":
        return import_xlsx(workspace / mapping.source, workspace, mapping)
    if _session_factory is None:
        raise HubError("credential_missing", "test-management credential is missing")
    client, token, scopes = _session_factory()
    try:
        return _remote_cases(mapping, client, token, scopes)
    finally:
        client.close()


def _remote_cases(
    mapping: FieldMapping,
    client: httpx.Client,
    token: str,
    scopes: tuple[str, ...],
) -> tuple[CanonicalCase, ...]:
    reader = ReadOnlyClient(client, allowed_host=_host(mapping))
    if mapping.provider == "xray" and mapping.edition == "cloud":
        return cases_from_cloud(fetch_cloud(reader, token), mapping)
    if mapping.provider == "xray":
        payload = fetch_data_center(reader, base_url=mapping.base_url, token=token)
        return cases_from_data_center(payload, mapping)
    if mapping.provider == "testrail":
        payload = fetch_cases(
            reader,
            base_url=mapping.base_url,
            project_id=mapping.project_id,
            token=token,
        )
        return cases_from_payload(payload, mapping)
    if mapping.provider == "google_sheets":
        payload = fetch_values(
            reader,
            spreadsheet_id=mapping.spreadsheet_id,
            token=token,
            scopes=scopes,
        )
        return cases_from_values(payload, mapping)
    raise HubError("mapping_rejected", "provider format is not supported")


def _post_once(
    mapping: FieldMapping,
    *,
    execution_id: str,
    source_ids: tuple[str, ...],
    digest: str,
) -> None:
    if _session_factory is None or mapping.format != "api":
        raise HubError("publication_rejected", "publication was not sent")
    client, token, _scopes = _session_factory()
    try:
        post_once(
            client,
            _publish_url(mapping),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            body={
                "idempotency_key": digest,
                "execution_id": execution_id,
                "source_ids": list(source_ids),
            },
            allowed_host=_host(mapping),
        )
    finally:
        client.close()


def _publish_url(mapping: FieldMapping) -> str:
    if mapping.provider == "testrail":
        return mapping.base_url.rstrip("/") + "/index.php?/api/v2/add_results"
    if mapping.provider == "google_sheets":
        sheet = mapping.spreadsheet_id
        return f"https://sheets.googleapis.com/v4/spreadsheets/{sheet}/values:append"
    if mapping.edition == "data_center":
        return mapping.base_url.rstrip("/") + "/rest/raven/1.0/import/execution"
    return "https://xray.cloud.getxray.app/api/v2/import/execution"


def _host(mapping: FieldMapping) -> str:
    if mapping.provider == "xray" and mapping.edition == "cloud":
        return "xray.cloud.getxray.app"
    if mapping.provider == "google_sheets":
        return "sheets.googleapis.com"
    host = urlsplit(mapping.base_url).hostname
    if host is None:
        raise HubError("connection_invalid", "provider host is missing")
    return host


def _workspace(profile: str | None) -> tuple[str, Path]:
    return workspace_for(load_config(), profile)


def _destination(workspace: Path, destination: str) -> Path:
    if destination.startswith(("/", "\\")) or ".." in destination.split("/"):
        raise HubError("path_rejected", "export path is outside the workspace")
    if not destination.endswith((".csv", ".xlsx")):
        raise HubError("mapping_rejected", "export format must be csv or xlsx")
    return workspace / "test-management" / destination


def _by_id(cases: tuple[CanonicalCase, ...], source_id: str) -> CanonicalCase:
    match = next((case for case in cases if case.source_id == source_id), None)
    if match is None:
        raise HubError("missing_field", "test case id was not found")
    return match


def _execution_id_ok(value: str) -> bool:
    cleaned = value.replace("-", "").replace("_", "")
    return bool(value) and cleaned.isalnum()


def _mutations(config: HubConfig, profile_id: str) -> bool:
    override = config.profiles[profile_id].execution.allow_mutations
    if override is not None:
        return override
    return config.execution.allow_mutations
