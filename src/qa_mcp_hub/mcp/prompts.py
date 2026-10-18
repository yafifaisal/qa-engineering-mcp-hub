"""Reusable MCP prompts implemented in Milestone 00.

Purpose: give clients a stable orientation prompt for truthful capability use.
Milestone: 00
Status: IMPLEMENTED
Ownership: mcp.prompts.orientation
Dependencies: none beyond FastMCP registration performed by the registry.
Expected tests: prompt discovery and rendered message content.
"""


def qa_hub_orientation() -> str:
    """Explain how to interpret Milestone 00 status and future capability claims."""
    return (
        "Use QA Engineering MCP Hub capability results conservatively. "
        "Treat only entries listed as implemented as callable. External providers "
        "and Milestones 01–11 are not implemented. Classify conclusions as "
        "VERIFIED, INFERRED, UNKNOWN, or CONFLICTING, and never treat AI prose as "
        "PASS/FAIL evidence."
    )
