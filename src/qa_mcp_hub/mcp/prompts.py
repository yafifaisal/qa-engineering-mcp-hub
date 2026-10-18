"""Reusable MCP prompts implemented in Milestone 00.

Purpose: give clients a stable orientation prompt for truthful capability use.
Milestone: 00
Status: IMPLEMENTED
Ownership: mcp.prompts.orientation
Dependencies: none beyond FastMCP registration performed by the registry.
Expected tests: prompt discovery and rendered message content.
"""


def qa_hub_orientation() -> str:
    """Explain how to interpret local capability status and future provider claims."""
    return (
        "Use QA Engineering MCP Hub capability results conservatively. "
        "Treat only entries listed as implemented as callable. Milestone 01 "
        "local configuration, profiles, and credential references are implemented. "
        "Milestone 02 provider contracts and local repository registration are "
        "implemented. Milestone 03 read-only GitHub, GitLab, Bitbucket, and "
        "Jira reads are implemented. Writes, Confluence, and Milestones 04–11 "
        "are not implemented. Classify conclusions as VERIFIED, INFERRED, "
        "UNKNOWN, or "
        "CONFLICTING, and never treat AI prose as PASS/FAIL evidence."
    )
