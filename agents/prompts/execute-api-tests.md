# Plan or execute a registered API suite

Status: **NOT_IMPLEMENTED — Future Milestone 06**

Until the runner, suite registry, and Bruno/Postman adapters are implemented,
return `NOT_IMPLEMENTED` and do not run a command. Never accept an arbitrary
executable, working directory, environment, collection path, or shell string.

When the milestone is implemented, resolve only a registered suite ID, enforce
the workspace policy and timeout, redact output, and keep invocation SUCCESS
separate from assertion PASSED/FAILED results.
