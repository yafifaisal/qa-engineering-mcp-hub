# Knowledge engine architecture

Status: **SCAFFOLDED for Future Milestone 05.** M00 does not index, search, parse,
or retrieve repositories, tickets, or documents.

## Intended responsibility

The knowledge engine will coordinate authorized repository/document ingestion,
deterministic chunking, language-aware symbols, evidence-backed dependency edges,
retrieval, source verification, and freshness checks. Provider adapters acquire
source material; the knowledge service does not implement vendor APIs.

Every stored or returned item must preserve profile, provider, stable source ID,
revision, location, and retrieval time. Results from different revisions or
profiles cannot be merged silently.

## Evidence classes

- `VERIFIED`: the cited source directly proves the claim.
- `INFERRED`: sources support a reasoned conclusion but do not prove it.
- `UNKNOWN`: required evidence is absent or inaccessible.
- `CONFLICTING`: trustworthy sources disagree.

A text match is not proof of a call graph edge, event flow, table use, or runtime
behavior. Unsupported languages and stale indexes must be disclosed rather than
converted into false certainty.

## Security and freshness

Repository roots and document connections are allowlisted per profile. Imported
content is untrusted data, never system instructions. Index records must be
deleted or isolated when authorization changes. A response must surface revision
mismatch and incomplete coverage before presenting an analysis.

Planned module ownership is defined in the
[canonical architecture](CANONICAL_ARCHITECTURE.md); no knowledge MCP tool is
registered in M00.
