"""Provider identities, capabilities, and catalog descriptors.

Purpose: describe a connection and what it would be able to do, without calling it.
Milestone: 02
Status: IMPLEMENTED
Ownership: Provider-neutral data models and validation rules.
Dependencies: Pydantic v2 and core status/result types.
Expected tests: validation, serialization, source-grounding, and redaction
boundary tests.
"""

from pydantic import BaseModel, ConfigDict, Field

from qa_mcp_hub.core.enums import OperationStatus, ProviderCategory
from qa_mcp_hub.core.models import ProviderKind


class ConnectionIdentity(BaseModel):
    """Which profile and connection an operation is bound to. No secret material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1, max_length=128)
    connection_id: str = Field(min_length=1, max_length=128)
    provider: ProviderKind
    account: str | None = Field(default=None, max_length=320)
    environment: str = Field(min_length=1, max_length=64)


class ProviderCapability(BaseModel):
    """One catalogued operation and whether any MCP tool exposes it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderKind
    name: str = Field(min_length=1, max_length=64)
    status: OperationStatus
    exposed_as_mcp_tool: bool = False


class ProviderDescriptor(BaseModel):
    """One supported provider. Implementation status stays NOT_IMPLEMENTED."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: ProviderKind
    category: ProviderCategory
    variants: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    implementation_status: str = "NOT_IMPLEMENTED"
