# Kafka assertions

Register an allowlisted topic, a bounded message cap, and a correlation key.
The consumer group must start with `qa-mcp-observer-`. Observation does not
commit offsets. A published event is not confirmed consumer completion.
