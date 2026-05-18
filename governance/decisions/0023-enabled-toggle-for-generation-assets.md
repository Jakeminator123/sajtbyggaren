# ADR 0023: Enabled-toggle för generationstillgångar

- Status: accepterat
- Datum: 2026-05-17

## Kontext

Backoffice behöver en säker operator-yta för att tillfälligt stänga av en
Scaffold, Scaffold Variant, Dossier eller Starter utan att radera filer eller
ändra historiska körningar. Det behövs särskilt när en tillgång finns på disk
men inte ska få väljas av planeringen eller användas av en pinned Project
Input.

Tidigare fanns ingen gemensam gate. En Scaffold kunde ligga i registret, en
Variant kunde ligga under `variants/`, en Dossier kunde finnas som manifest och
en Starter kunde finnas under `data/starters/` utan att Backoffice hade ett
enkelt sätt att markera den som inaktiv.

## Beslut

- `enabled: bool` läggs till på:
  - entries i `scaffold-contract.v1.json:primaryScaffoldRegistry`
  - Scaffold Variant-filer
  - Dossier-manifest
  - entries i nya `starter-registry.v1.json`
- Saknat `enabled` behandlas som `true` av runtime för bakåtkompatibilitet.
  Nya och redigerade entries ska skriva fältet explicit.
- Planning filtrerar bort disabled tillgångar innan den väljer Scaffold,
  Variant, Dossier eller Starter.
- En pinned Project Input som pekar på en disabled tillgång ska faila tydligt
  innan genereringen fortsätter. Det är bättre än att tyst falla tillbaka till
  något annat och bryta operatorns val.
- Starter-toggle bor i governance, inte i `data/starters/`, eftersom
  starter-innehåll är körbar bas och ofta vendored. Toggle-state är policy,
  inte källkod i startern.

## Schema- och policyändringar

- `governance/schemas/scaffold-contract.schema.json` tillåter `enabled`.
- `governance/schemas/dossier.schema.json` kräver `enabled` för nya
  Dossier-manifest.
- `governance/schemas/starter-registry.schema.json` introduceras.
- `governance/policies/starter-registry.v1.json` introduceras som formell
  enabled-gate för Starters.

## Konsekvenser

- Backoffice kan toggla generationstillgångar utan att röra
  `data/starters/`-innehåll eller ta bort filer.
- Äldre tillgångar utan fältet fortsätter fungera tills de redigeras.
- Tester måste täcka både filter-beteendet och fail-loud-beteendet för pinned
  Project Input.
