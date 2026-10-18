"""Typed framework errors that stay safe to display.

Purpose: represent failures without secrets or provider response bodies.
Milestone: 02
Status: IMPLEMENTED
Ownership: core.errors
Dependencies: Core enums and source-reference contracts.
Expected tests: error mapping, safe rendering, causal preservation, and redaction.
"""

from qa_mcp_hub.core.enums import OperationStatus


class HubError(Exception):
    """Base error whose message is already safe to show to a user."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class UnsupportedCapabilityError(HubError):
    """The requested provider operation is absent or not implemented."""

    def __init__(self, provider: str, capability: str, *, implemented: bool) -> None:
        self.provider = provider
        self.capability = capability
        status = (
            OperationStatus.not_implemented
            if implemented
            else OperationStatus.unsupported
        )
        self.status = status
        super().__init__(
            status.value,
            f"{provider} capability {capability} is {status.value}",
        )


class UnknownProviderError(HubError):
    """The provider identifier is outside the canonical catalog."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__("unknown_provider", f"unknown provider: {provider}")


class ProviderResolutionError(HubError):
    """A connection cannot be bound inside the requested profile."""

    def __init__(self, message: str) -> None:
        super().__init__("provider_resolution", message)


class CatalogMismatchError(HubError):
    """The declared provider catalog does not match the architecture."""

    def __init__(self, message: str) -> None:
        super().__init__("catalog_mismatch", message)


class PathAllowlistError(HubError):
    """A filesystem path escaped an explicitly approved root."""

    def __init__(self, message: str = "path is outside an approved root") -> None:
        super().__init__("path_allowlist", message)


class RepositoryRegistryError(HubError):
    """Registration rejected a duplicate, ambiguous, or foreign repository."""

    def __init__(self, message: str) -> None:
        super().__init__("repository_registry", message)


class GitInspectionError(HubError):
    """Local Git metadata could not be read with the bounded git command."""

    def __init__(self, message: str) -> None:
        super().__init__("git_inspection", message)


class ProviderRequestError(HubError):
    """A provider HTTP failure whose message does not include the response body."""

    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(code, message)


class RetryRejectedError(HubError):
    """A retry decision refused another attempt."""

    def __init__(self, message: str) -> None:
        super().__init__("retry_rejected", message)
