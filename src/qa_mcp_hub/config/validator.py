"""Safe diagnostics for complete Milestone 01 user configuration.

Purpose: reject invalid or secret-bearing documents without echoing values.
Milestone: 01
Status: IMPLEMENTED
Ownership: config.validator
Dependencies: Pydantic validation errors.
Expected tests: plaintext field rejection and value-free diagnostics.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from qa_mcp_hub.config.models import HubConfig

_FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "client_secret",
        "password",
        "refresh_token",
        "secret",
        "token",
    }
)


@dataclass(frozen=True, slots=True)
class ConfigIssue:
    """One value-free validation diagnostic safe for a terminal or log."""

    severity: Literal["ERROR", "WARNING"]
    code: str
    location: str
    message: str


@dataclass(frozen=True, slots=True)
class ConfigValidationReport:
    """Validation outcome with redaction-safe diagnostics."""

    valid: bool
    issues: tuple[ConfigIssue, ...]
    config: HubConfig | None = None


class ConfigValidationError(ValueError):
    """Raised for an invalid or secret-bearing configuration mapping."""

    def __init__(self, issues: tuple[ConfigIssue, ...]) -> None:
        self.issues = issues
        super().__init__("configuration validation failed")


def _location(parts: Sequence[str | int]) -> str:
    if not parts:
        return "$"
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


def _find_forbidden_secret_keys(
    value: object,
    location: tuple[str | int, ...] = (),
) -> list[ConfigIssue]:
    issues: list[ConfigIssue] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            safe_key = str(key)
            child_location = (*location, safe_key)
            if safe_key.casefold() in _FORBIDDEN_SECRET_KEYS:
                issues.append(
                    ConfigIssue(
                        severity="ERROR",
                        code="plaintext_secret_field",
                        location=_location(child_location),
                        message=(
                            "plaintext credential fields are forbidden; use a reference"
                        ),
                    )
                )
            issues.extend(_find_forbidden_secret_keys(child, child_location))
    elif isinstance(value, list | tuple):
        for index, child in enumerate(value):
            issues.extend(_find_forbidden_secret_keys(child, (*location, index)))
    return issues


def inspect_config(document: Mapping[str, Any] | HubConfig) -> ConfigValidationReport:
    """Return value-free diagnostics instead of leaking rejected configuration."""
    if isinstance(document, HubConfig):
        raw: Mapping[str, Any] = document.model_dump(mode="python")
    else:
        raw = document

    secret_issues = tuple(_find_forbidden_secret_keys(raw))
    if secret_issues:
        return ConfigValidationReport(valid=False, issues=secret_issues)

    try:
        config = HubConfig.model_validate(dict(raw))
    except ValidationError as exc:
        issues = tuple(
            ConfigIssue(
                severity="ERROR",
                code=str(error["type"]),
                location=_location(error["loc"]),
                message="value does not satisfy the configuration contract",
            )
            for error in exc.errors(
                include_url=False, include_context=False, include_input=False
            )
        )
        return ConfigValidationReport(valid=False, issues=issues)
    return ConfigValidationReport(valid=True, issues=(), config=config)


def validate_config(document: Mapping[str, Any] | HubConfig) -> HubConfig:
    """Validate a configuration or raise a redaction-safe typed error."""
    report = inspect_config(document)
    if not report.valid or report.config is None:
        raise ConfigValidationError(report.issues)
    return report.config
