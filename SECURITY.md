# Security policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private URLs, or
customer data. Contact the project maintainers through the repository's private
security-reporting channel. Until a public hosting location is established, report
the issue privately to the repository owner and include affected versions, impact,
and a minimal redacted reproduction.

## Supported versions

| Version | Status |
|---|---|
| 0.1.0 | Development Community Edition. Not published to PyPI. |

There is no public support window yet. A tag must be `v` plus the version in
`pyproject.toml`. CI does not create tags. The release workflow builds artifacts
on a tag or on manual dispatch. The publish job runs only when the dispatch input
is exactly `APPROVE_PUBLIC_RELEASE` and the protected `pypi` environment approves
trusted publishing. This repository has not been published.

## Security boundaries

The server speaks stdio. Provider adapters that exist are read-oriented or
approval-gated, and their live calls are not claimed. Configuration examples
contain credential references only. `scripts/build_package.py` writes a CycloneDX
SBOM and scans the wheel and source distribution for known token shapes and
unsafe archive paths. A clean scan does not prove that arbitrary text contains no
sensitive business data.

See the [threat model](docs/security/THREAT_MODEL.md),
[permissions model](docs/security/permissions.md), and
[data-handling rules](docs/security/data-handling.md).
