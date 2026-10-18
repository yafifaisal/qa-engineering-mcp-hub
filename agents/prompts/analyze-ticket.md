# Analyze a ticket for QA planning

Status: **NOT_IMPLEMENTED — Future Milestone 03**

Use this prompt only after an authorized ticket adapter and grounded source
resolver are implemented. If the issue cannot be read through an approved
profile, stop and report the missing capability; do not infer ticket contents.

## Inputs

- Ticket reference and approved connection ID
- Repository IDs or documentation sources explicitly in scope
- Requested change revision, when known

## Required output

Separate VERIFIED, INFERRED, UNKNOWN, and CONFLICTING findings. Cite the ticket
and exact source revisions, identify deterministic acceptance criteria, list
test risks and missing information, and label any proposed scenario as a plan —
not as executed evidence.
