# Knowledge engine architecture

Status: **IMPLEMENTED and OFFLINE_VERIFIED for local checkouts.** No live
provider call is claimed.

## Responsibility

The knowledge engine indexes git-tracked files inside an approved profile
checkout, chunks them with line provenance, extracts symbols, records dependency
edges that the parser can support, and retrieves by exact keyword. An optional
`EmbeddingProvider` can be injected. Community Edition does not call a hosted
embedding service. Provider adapters acquire remote documents; the engine stores
a document only when the caller supplies the record.

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

Python parsing is VERIFIED from the standard-library AST. Go, Java, JavaScript,
and TypeScript pattern parsing is INFERRED. Every other language is UNKNOWN.
Identical `CLAIM key=value` lines are compared across indexed sources; general
prose is not treated as a contradiction. MCP tools `search_knowledge`,
`find_implementation`, and `trace_cross_repo_flow` read this index. They do not
execute tests or create workflows. `complete_graph` is always false.
