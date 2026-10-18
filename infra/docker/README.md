# Optional local container

Status: **SCAFFOLDED**. Containers are not required to install, test, build, or
run Milestone 00. The root `Dockerfile` packages the existing local stdio server
only; it does not enable remote MCP transport or any provider integration.

Build manually when Docker is available:

```sh
docker build -t qa-engineering-mcp-hub:local .
```

The container runs as a non-root user and has no network listener or declared
port. Supplying credentials, mounting a QA Workspace, and remote hosting are out
of scope for Milestone 00.
