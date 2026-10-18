---
name: api-testing
description: Operate approved registered Bruno or Postman suites with bounded execution after the API runner milestone is implemented.
metadata:
  owning-milestone: "06"
  implementation-status: NOT_IMPLEMENTED
---

# API testing

This repository skill is scaffolded for Future Milestone 06. In Milestone 00,
return `NOT_IMPLEMENTED`; do not invoke Bruno, Postman, Newman, a shell, or any
other process.

Future execution must resolve a fixed registered suite, use argument arrays,
restrict the working directory and environment, enforce time and output limits,
redact evidence, and normalize individual assertion results. A zero process exit
or HTTP 2xx response is not by itself a passed test.
