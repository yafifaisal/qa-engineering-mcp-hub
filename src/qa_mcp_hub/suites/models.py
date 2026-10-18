"""Approved suite identities and registry documents.

Purpose: type suite ids, runners, paths, and allowed operations.
Milestone: 06
Status: IMPLEMENTED
Ownership: suites.models
Dependencies: Pydantic v2.
Expected tests: validation, safe paths, and serialization.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CredentialBinding(BaseModel):
    """A variable name and a credential reference. The value is not stored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    reference: str


class SuiteDefinition(BaseModel):
    """One registered Bruno or Postman suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    runner: Literal["bruno", "postman"]
    path: str
    environment: str | None = None
    enabled: bool
    version: str = "1"
    allowed_operation: Literal["read", "mutate"] = "read"
    assertion_ids: tuple[str, ...] = ()
    credential_env: tuple[CredentialBinding, ...] = ()


class SuiteRegistryFile(BaseModel):
    """The suites.yaml document inside a QA Workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    implementation_status: Literal["SCAFFOLDED", "IMPLEMENTED"]
    suites: tuple[SuiteDefinition, ...] = ()


class CollectionDiscovery(BaseModel):
    """Files found at a registered suite path. Discovery does not execute them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str
    runner: Literal["bruno", "postman"]
    path: str
    files: tuple[str, ...] = ()
    found: bool


class SuiteCatalog(BaseModel):
    """Registered suites plus the collections discovered at their paths."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    registry_status: Literal["SCAFFOLDED", "IMPLEMENTED"]
    executable: bool
    suites: tuple[SuiteDefinition, ...] = ()
    discovered: tuple[CollectionDiscovery, ...] = ()


class ResolvedSuite(BaseModel):
    """Immutable suite plan captured when a run is submitted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite: SuiteDefinition
    collection_path: str
    working_directory: str
    source_revision: str | None
    argv: tuple[str, ...] = Field(min_length=1)
