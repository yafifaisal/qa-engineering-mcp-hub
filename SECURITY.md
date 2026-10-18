# Security policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, private URLs, or
customer data. Contact the project maintainers through the repository's private
security-reporting channel. Until a public hosting location is established, report
the issue privately to the repository owner and include affected versions, impact,
and a minimal redacted reproduction.

## Supported versions

No stable public release exists yet. Security fixes apply to the current development
branch until a version support policy is published.

## Security boundaries

Milestone 00 exposes only local read-only introspection over stdio. Provider access,
credential lifecycle, arbitrary process execution, arbitrary SQL, remote hosting,
and evidence publication are not implemented. Configuration examples contain
credential references only.

See the [threat model](docs/security/THREAT_MODEL.md),
[permissions model](docs/security/permissions.md), and
[data-handling rules](docs/security/data-handling.md).
