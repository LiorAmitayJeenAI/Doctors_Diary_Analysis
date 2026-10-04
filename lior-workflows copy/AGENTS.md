# Lior Langflow Workflows

## Repository purpose

This repository documents, patches, tests, and deploys two remote Langflow workflows:

- `Analytics - Lior` (`db3bfc7e-572b-4388-9642-1716f094a066`)
- `Recommendation - Lior` (`e8e69eb0-6607-4bec-8117-386cb861900e`)

This is not the application source code. Python files under `tools/` generate or deploy
changes to Python components embedded inside the remote Langflow graphs. A local change
does not change Langflow until it is explicitly deployed and verified.

## Required context

Before analyzing or changing a workflow, read:

- `ANALYTICS-LIOR.md` for Analytics architecture, contracts, and component ownership.
- `RECOMMENDATION-LIOR.md` for Recommendation architecture, rendering, and validation.

Keep those documents accurate when behavior or contracts change. Do not duplicate their
detailed architecture in this file.

## Workflow boundaries

- Analytics deterministically calculates evidence, decision tiers, candidate IDs,
  metric paths, calendar-setting context, and persisted metrics.
- Recommendation loads persisted Analytics results, validates evidence and business
  rules, and renders the client-facing Hebrew report.
- LLM agents may phrase approved candidates but must not promote insights into
  recommendations or invent quantities.
- Preserve working days, total working hours, stable IDs, and metric paths unless the
  requested change explicitly changes their contract.

## Langflow compatibility

Every change must be compatible with **Langflow 1.9.2**.

- Preserve Langflow 1.9.2 component imports, input/output types, and connector types.
- Syntax-check every modified embedded Python component.
- Do not use APIs or serialized graph fields introduced after Langflow 1.9.2.
- Preserve graph topology unless a topology change is explicitly required.

## Safe change and deployment procedure

1. Fetch the latest live workflow before preparing a remote change.
2. Change only the components required by the request.
3. Verify embedded Python, tests, node IDs, edges, and expected connector return types.
4. Re-fetch immediately before deployment and abort if the live graph changed.
5. Patch only the intended workflow data, then re-fetch and verify the deployed hash.
6. Never commit or retain API keys, JWTs, credentials, or secret-bearing snapshots.
7. Do not claim a local patch was deployed unless live verification succeeded.

## Mandatory completion report

After every workflow change, report:

- Deployment status: local only, or deployed and verified.
- Exact workflow name as stored in Langflow.
- Every changed component using its exact `display_name` value.
- Component node ID in parentheses when available.
- Verification performed and any remaining validation gap.

Example:

```text
Workflow: Recommendation - Lior
Changed components:
- Recommendation Presenter – Friendly Hebrew (recommendation_presenter-TuUXM)
Status: deployed and verified
```
