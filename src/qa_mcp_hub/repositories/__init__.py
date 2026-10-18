"""Repository registration namespace.

Purpose: export registration, discovery, and validation without indexing files.
Milestone: 02
Status: IMPLEMENTED
Ownership: repositories.package
Dependencies: Git provider contracts, path policy, profiles, and storage.
Expected tests: import safety, profile isolation, and no Milestone 00 registration.
"""

from qa_mcp_hub.repositories.registry import (
    list_repositories,
    register_repository,
    remove_repository,
)

__all__ = ["list_repositories", "register_repository", "remove_repository"]
