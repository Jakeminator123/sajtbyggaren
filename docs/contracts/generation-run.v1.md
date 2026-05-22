# generation-run.v1

Status: draft contract for Team Parallel Work v1.

Syfte: ge Viewser och backend en gemensam shape för en generation run så att
frontend kan bygga status- och preview-UI mot mockar innan backend är färdig.

## Ägare

- Backend/run-state: Jakob.
- Frontend-presentation: frontend-medutvecklare.
- Contract-review: båda.

## Input

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `projectId` | `string` | Ja | Stabilt projekt-id. |
| `prompt` | `string` | Ja | Init prompt eller aktuell användarprompt. |
| `followUpPrompt` | `string` | Nej | Bara vid följdprompt/versionering. |

## Output

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `runId` | `string` | Ja | Stabilt id för körningen. |
| `projectId` | `string` | Ja | Samma projekt som input. |
| `version` | `number` | Ja | Versionen som runnen skapar eller uppdaterar. |
| `status` | `"queued" | "running" | "ready" | "failed"` | Ja | UI-status. |
| `previewUrl` | `string | null` | Nej | Sätts när preview finns. |
| `filesSummary` | `object | null` | Nej | Kort summering av genererade filer. |
| `qualityStatus` | `"pending" | "passed" | "warning" | "failed" | null` | Nej | Samlad quality/eval-signal. |
| `errorMessage` | `string | null` | Nej | Användbar feltext för UI. |

## Mock success

```json
{
  "runId": "run_demo_001",
  "projectId": "project_demo_001",
  "version": 2,
  "status": "ready",
  "previewUrl": "/preview/project_demo_001/v2",
  "filesSummary": {
    "pages": 5,
    "components": 8,
    "warnings": 0
  },
  "qualityStatus": "passed",
  "errorMessage": null
}
```

## Mock loading

```json
{
  "runId": "run_demo_001",
  "projectId": "project_demo_001",
  "version": 2,
  "status": "running",
  "previewUrl": null,
  "filesSummary": null,
  "qualityStatus": "pending",
  "errorMessage": null
}
```

## Mock error

```json
{
  "runId": "run_demo_001",
  "projectId": "project_demo_001",
  "version": 2,
  "status": "failed",
  "previewUrl": null,
  "filesSummary": null,
  "qualityStatus": "failed",
  "errorMessage": "Generation kunde inte slutföras. Försök igen eller öppna Run Details."
}
```

## Testidé

- Contract test: validera att backend-output alltid har `runId`, `projectId`,
  `version` och ett tillåtet `status`.
- Frontend test: rendera loading, ready och failed mot mockarna utan backend.
- Regression: en ny `status` får inte läggas till utan contract-uppdatering.
