from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ProviderKind(StrEnum):
    github = 'github'
    gitlab = 'gitlab'
    bitbucket = 'bitbucket'
    jira = 'jira'
    confluence = 'confluence'
    google_docs = 'google_docs'
    bruno = 'bruno'
    postman = 'postman'
    postgresql = 'postgresql'
    mysql = 'mysql'
    kafka = 'kafka'
    bitbucket_pipelines = 'bitbucket_pipelines'
    github_actions = 'github_actions'
    jenkins = 'jenkins'
    xray = 'xray'
    testrail = 'testrail'
    spreadsheet = 'spreadsheet'


class Connection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1)
    provider: ProviderKind
    base_url: str | None = None
    credential_ref: str | None = None  # reference only
    enabled: bool = True


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    connections: list[Connection] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_connections(self) -> 'Profile':
        ids = [item.id for item in self.connections]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate connection id in profile')
        return self


class HubConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    active_profile: str
    profiles: dict[str, Profile]

    @model_validator(mode='after')
    def active_profile_exists(self) -> 'HubConfig':
        if self.active_profile not in self.profiles:
            raise ValueError('Active profile does not exist')
        return self
