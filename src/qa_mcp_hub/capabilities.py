"""Explicit implemented-versus-planned capability catalog."""

from pydantic import BaseModel, ConfigDict


class CapabilityCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)
    implemented: tuple[str, ...]
    planned: tuple[str, ...]


def list_capabilities() -> CapabilityCatalog:
    return CapabilityCatalog(
        implemented=("hub_health", "hub_capabilities"),
        planned=(
            "profiles_and_credentials",
            "github_gitlab_bitbucket",
            "jira_confluence_google_docs",
            "bruno_postman",
            "postgresql_mysql_kafka",
            "bitbucket_pipelines_github_actions_jenkins",
            "xray_testrail_spreadsheet",
            "qa_evidence_and_release",
        ),
    )
