# Generic QA Workspace template

Status: **SCAFFOLDED for future milestones; no workflow, suite, assertion, CI
mapping, or provider integration in this directory is executable in Milestone
00.**

Copy this directory outside the framework repository to create a
company-specific QA Workspace. Keep business flows, repository mappings, and
approved test assets in that copy. Machine-specific paths, connection profiles,
and credential references belong in user configuration, not here. Secret values
must remain in an approved credential store.

## Directory ownership

- `workflows/` holds approved orchestration definitions. The API and E2E folders
  contain README guidance until their owning milestones are implemented.
- `suites/` registers fixed Bruno or Postman asset paths; it never accepts an
  arbitrary command string.
- `assertions/` holds deterministic checks. AI-generated conclusions are not
  PASS/FAIL evidence.
- `evidence-policies/` declares which checks are required and how missing
  evidence is classified.
- `test-management/` holds reviewed mappings and import templates.
- `ci/` holds allowlisted job and pipeline identifiers. It does not authorize a
  pipeline trigger.
- `knowledge/` holds company-owned context with source and freshness metadata.

Every leaf directory includes a README instead of an unexplained placeholder.
Replace that README only when a real, reviewed asset is added. Examples remain
disabled until the corresponding implementation and tests are complete.
