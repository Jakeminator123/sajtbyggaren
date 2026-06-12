# Arkiv: current-focus-block 2026-06-12 ~07:30 (morgonpasset, B199 v2)

Flyttat hit från `docs/current-focus.md` när förmiddagspasset (hostad
preview-standardisering, ADR 0055) tog över som aktuellt block.

## Status nu (2026-06-12 ~07:30 — B199 v2: hostad run-historik + artefakt-läsning + omladdnings-återställning)

**Git:** `main = jakob-be` (rent träd, local == origin). B199 v2-passet är
landat direkt på `jakob-be` på operatörsmandat och synkat till `main`.
Production deployar från `main`. Ingen tarball-omladdning behövs — passet
rör bara `apps/viewser/` + tester/docs (orkestrerings-skriptet genereras av
TS-koden, inte av build-context-tarballen).

**Landat i morgonpasset (B199 v2, operatörsmandat efter bannerfrågan):**

- **Hostad run-historik/artefakter/inspector:** orkestrerings-skriptet
  publicerar durabelt KV-index (`HostedRunIndexEntry`, naming-dictionary
  v39) per lyckat bygge; ny `lib/hosted-run-history.ts` läser indexet +
  artefakt-tarballen från blob; `/api/runs?siteId=` (siteId =
  capability-nyckel, ingen global listning) + artifacts/trace serveras
  hostat. B199 STÄNGD i known-issues.
- **Omladdnings-återställning:** builder-valet persisteras i
  sessionStorage och återställs efter hård reload (lokalt + hostat).
  Bannern är eget fält (`hostedBanner`) och armar aldrig 404-latchen;
  banner-texten omskriven till nya läget.
- **Init-paritet + historisk baseRunId:** init-svar bär kanonisk
  build_site-runId; historisk `baseRunId` hydrerar sin egen versions
  artefakter via runId-indexet (siteId-bundet).
- 14 nya källkods-lås i `tests/test_viewser_hosted_run_history.py`.

Last verified state: `261f0c63` (2026-06-12 ~09:10 UTC+2; B199 v2-kodcommiten
på `jakob-be`, synkas till `main` i samma push — rent träd, full svit
(`pytest -n auto`) + ruff + governance + term-coverage + tsc + eslint gröna
lokalt).
