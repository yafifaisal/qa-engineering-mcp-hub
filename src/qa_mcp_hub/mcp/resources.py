"""Read-only MCP resources implemented in Milestone 00.

Purpose: expose deterministic server status as client-readable context.
Milestone: 00
Status: IMPLEMENTED
Ownership: mcp.resources.status
Dependencies: JSON and the local health/capability functions.
Expected tests: resource discovery, URI, MIME type, and decoded content.
"""

import json

from qa_mcp_hub.mcp.tools.system import hub_capabilities, hub_health

STATUS_RESOURCE_URI = "qa-hub://status"


def hub_status_resource() -> str:
    """Render local hub status as stable JSON with no machine secrets."""
    payload = {
        "health": hub_health().model_dump(mode="json"),
        "capabilities": hub_capabilities().model_dump(mode="json"),
        "external_integrations": (
            "git_jira_docs_read_only_local_knowledge_registered_e2e_ci_read_test_cases_evidence"
        ),
    }
    return json.dumps(payload, sort_keys=True)
