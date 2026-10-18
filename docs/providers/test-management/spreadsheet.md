# CSV and XLSX spreadsheet provider

> Current status: **NOT_IMPLEMENTED**  
> Owning milestone: **09**  
> Verification: documentation scaffold only; no provider request or file operation has occurred.

## 1. Provider overview

The spreadsheet provider covers local CSV and XLSX interchange for test cases. It is a file-format adapter, not a general spreadsheet execution engine or cloud-storage integration.

## 2. Supported editions

Supported targets are explicitly registered CSV files and XLSX workbooks. Exact dialects, encodings, workbook features, and library versions require verification and configuration.

## 3. Cloud/self-hosted differences

Cloud/self-hosted does not apply to local files. Files synchronized by third-party drives remain local inputs; their sync, sharing, and permission systems are outside this adapter.

## 4. Supported API capabilities

Planned capabilities are previewed import, explicit column mapping, normalized test-case conversion, loss reporting, safe export, external-ID preservation, and no implicit overwrite.

These are planned capabilities, not current support.

## 5. Authentication methods

Local files do not use provider tokens. Filesystem access is authorized through registered QA Workspace paths and OS permissions; encrypted workbook support requires verification and is not assumed.

**Requires verification:** confirm exact current authentication behavior immediately before implementation.

## 6. Required permissions

Grant read access only to registered import files/directories and write access only to explicit export targets after approval. Reject path traversal and symlink escapes.

**Requires verification:** record exact scope, grant, role, or filesystem permissions in the implementation milestone.

## 7. Credential configuration

Configuration may contain only a credential reference. Secrets must be resolved inside the future adapter and must not appear in MCP arguments, logs, reports, exported files, or source control.

## 8. Connection configuration example

Illustrative future shape only; Milestone 00 does not load or validate this connection:

```yaml
connections:
  - id: spreadsheet-local
    provider: spreadsheet
    enabled: true
```

## 9. Setup instructions

Register mapping definitions and fixed input/output roots in the future QA Workspace, select encoding/dialect or sheet/table explicitly, preview conversion, review loss warnings, then approve export if needed.

Stop during Milestone 00: the scaffold cannot authenticate, connect, read, write, or execute.

## 10. Windows/macOS/Linux considerations

Newlines, default encodings, path syntax, file locks, case sensitivity, Excel behavior, and formula handling differ across Windows, macOS, and Linux. Use `pathlib` and native tests.

## 11. MCP tools using this provider

No MCP tool uses spreadsheets in Milestone 00. Future test-management tools may preview imports and produce an explicitly approved export through registered mappings.

## 12. Read/write authorization behavior

Import is read-only. Export must use a new or explicitly approved destination, atomic replacement where allowed, backup/collision policy, and no silent overwrite.

## 13. Pagination and rate limiting

Files are processed with explicit row, sheet, column, cell-size, and total-size limits rather than API pagination. Large workbooks require bounded streaming behavior where supported.

## 14. Timeout and retry behavior

Apply file-size and processing deadlines; do not retry malformed or locked files indefinitely. Writes must be atomic and failures must leave the original intact.

## 15. Expected error handling

Normalize missing/denied/path-escape, unsupported encoding/format, malformed rows, formulas, duplicate IDs, mapping loss, locked file, size limit, and write-collision errors.

## 16. Security considerations

Restrict paths, reject unsafe formulas on export, avoid evaluating formulas/macros, cap decompression/resources, sanitize cell content, redact PII, and preserve provenance/checksums.

## 17. Troubleshooting

Check registered path, OS permission/lock, CSV encoding/dialect/newline, XLSX sheet/table, headers, duplicate IDs, formulas, mapping definition, and size limits.

Because the provider is not implemented, current inability to connect or operate is expected.

## 18. Related implementation files

- `src/qa_mcp_hub/adapters/test_management/spreadsheet.py` — SCAFFOLDED; docstring only.
- `src/qa_mcp_hub/providers/contracts.py` — SCAFFOLDED provider-neutral contract owner.
- `src/qa_mcp_hub/providers/registry.py` — SCAFFOLDED allowlist/factory owner.

## 19. Related tests

Planned path-escape, CSV dialect/encoding, XLSX mapping, empty/malformed cells, formula safety, duplicate IDs, round-trip/loss report, collision, and native-OS tests.

No test currently validates a real provider integration.

## 20. Current implementation status

**NOT_IMPLEMENTED.** The adapter file is **SCAFFOLDED** and contains no client, connection, file, query, parsing, publication, or registration logic. It is not exposed through FastMCP.

## 21. Official documentation references

- [Python CSV library](https://docs.python.org/3/library/csv.html)
- [RFC 4180 CSV format](https://www.rfc-editor.org/rfc/rfc4180)
- [Microsoft XLSX specification overview](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-xlsx/)

Endpoint, version, permission, quota, and format details marked above require verification against current official sources before implementation.

