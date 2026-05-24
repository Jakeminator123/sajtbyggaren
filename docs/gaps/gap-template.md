# Gap-template

```yaml
id: GAP-...
type: Gap/UI
owner: jakob
title: Kort titel
whyNow: Varför detta är rätt nästa steg.
paths:
  - docs/example.md
doNotTouch:
  - packages/generation/**
acceptanceCriteria:
  - Tydligt verifierbart resultat.
checks:
  - python scripts/sprintvakt_check.py
collisionRisk: green
reviewer: jakob
status: queued
createdAt: 2026-05-24T00:00:00Z
updatedAt: 2026-05-24T00:00:00Z
notes:
  - Kort arbetsnotis.
```

## Fält

- `id`: stabilt gap-id, helst `GAP-<kort-namn>`.
- `type`: en av `Gap/UI`, `Gap/Flow`, `Gap/Guard`, `Gap/Polish`, `Gap/Docs` eller `Gap/Runtime`.
- `owner`: `jakob`, `christopher`, `steward` eller `scout`.
- `title`: en rad som beskriver arbetet.
- `whyNow`: varför gapet ska tas nu.
- `paths`: filer eller globbar som gapet behöver röra.
- `doNotTouch`: närliggande filer/områden som uttryckligen är utanför scope.
- `acceptanceCriteria`: verifierbara krav innan gapet är klart.
- `checks`: kommandon eller manuella kontroller som ska köras.
- `collisionRisk`: `green`, `yellow` eller `red`.
- `reviewer`: `jakob`, `christopher` eller `both`.
- `status`: `queued`, `active` eller `completed`.
- `createdAt` och `updatedAt`: ISO-tid.
- `notes`: korta praktiska notiser.
