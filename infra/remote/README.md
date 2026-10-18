# Remote deployment scaffold

Status: **NOT_IMPLEMENTED — future milestone**.

Milestone 00 supports local stdio only. There is no remote HTTP transport,
authentication gateway, multi-user authorization, TLS termination, persistent
store, telemetry pipeline, or production deployment in this repository. The
example environment file contains non-secret policy values and credential
reference names only; it is not a runnable deployment configuration.

Before remote deployment is implemented, define and test tenant isolation,
authentication, authorization, rate limits, audit retention, TLS, secret-store
integration, health semantics, and incident response. Never expose a local stdio
server directly to a network.
