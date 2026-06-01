# Christopher-handoff: ärlig follow-up-feedback i FloatingChat (ADR 0034 väg B)

Datum: 2026-06-01. Avsändare: backend-agenten (`jakob-be`). Din branch: `christopher-ui`.

## Kontext

Backend för ADR 0034 väg A är klar och pushad (`641abc9` på `jakob-be`): en
följdprompt blir nu antingen en synlig sajt-ändring (via `copyDirectives`)
eller en ärlig no-op-signal i artefakterna. Det som saknas är presentationen i
FloatingChat. Du äger den ytan. Rör inte backend/generation.

## Backend-kontraktet du läser (finns redan, inget nytt behövs)

Per follow-up-build skriver buildern till `build-result.json`:

- `appliedVisibleEffect` (boolean) — `true` om följdprompten gav en synlig
  ändring i `app/page.tsx`, annars `false`. Saknas helt på init-builds.
- `appliedVisibleEffectReason` (string) — en av `visible_files_changed`,
  `visible_files_unchanged`, `intent_no_semantic_change`,
  `semantic_intent_without_previous_snapshot`.
- Trace-event `followup.no_op_detected` (status `warning`) i `trace.ndjson`
  när ingen synlig effekt fångades.

Den applicerade ändringen (när den finns) ligger i versionens project-input
under `directives.copyDirectives` — en lista av objekt:

- `target`: `company-name` eller `tagline`
- `operation`: `replace-text` eller `include-token`
- `payload`: den nya texten / token (validerad sträng, redan läck-säker)
- `source`: `prompt-rule`, `llm` eller `explicit`

Du har redan trace-endpointen (`apps/viewser/app/api/runs/[runId]/trace/route.ts`)
och kan exponera `build-result`-fälten samma väg.

## Vad du bygger (UI, christopher-ui)

1. Ärlig no-op-rad när `appliedVisibleEffect === false`: visa en lugn rad i
   FloatingChat, t.ex. "Jag kunde inte fånga någon synlig ändring den här
   gången. Testa att ange exakt rubrik, text eller sektion — t.ex. 'byt namnet
   i headern till X'." Signalera aldrig lyckad ändring när effekten uteblev.
2. Kort success-rad när `appliedVisibleEffect === true` och
   `directives.copyDirectives` finns: visa vad som ändrades, härlett ur
   `target` + `payload`:
   - `company-name` → "Jag ändrade företagsnamnet till '{payload}'."
   - `tagline` + `replace-text` → "Jag uppdaterade rubriken till '{payload}'."
   - `tagline` + `include-token` → "Jag la in '{payload}' i hero-texten."
   Rendera `payload` som escaped text, aldrig som rå HTML.

## Lane-disciplin

- Jobba på `christopher-ui`. Dina paths: `apps/viewser/components/**`,
  `apps/viewser/app/**/*.tsx`, `apps/viewser/app/**/*.css`,
  `apps/viewser/public/**`.
- Rör inte backend/generation (`scripts/**`, `packages/generation/**`,
  `governance/**`). Kontraktet ovan är låst. Behöver du ett nytt fält — be
  jakob-be lägga till det, ändra det inte själv.

## Test / acceptans

- Följdprompt "byt namnet i headern till X" → success-rad "Jag ändrade
  företagsnamnet till 'X'." och namnet syns i preview.
- Vag följdprompt ("gör sidan lite finare") → no-op-rad, ingen falsk success.
- Rå `payload` renderas escaped, aldrig som rå HTML.

## Referenser

- `governance/decisions/0034-followup-prompt-content-passthrough.md`
  (väg A landad, väg B = detta, väg C parkerad).
- `docs/gaps/GAP-followup-prompt-content-passthrough.md`.
- Backend-commit: `641abc9` på `jakob-be`.
