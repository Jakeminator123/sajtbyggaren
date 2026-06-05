# KÖR 0 — Preflight (mini, docs/verifiering — kör före 6a/1a)

> En kort verifieringsrunda **innan** kod-skivorna börjar, så agenterna inte bygger mot
> stale antaganden. Read-only + ev. liten docs-sync. Ingen produktkod.

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`03-preview-data-och-versioner.md`](03-preview-data-och-versioner.md),
`docs/current-focus.md`, `docs/handoff.md`.
**Beror på:** inget. Kör först.

---

## Mål

Bekräfta att verkligheten matchar det körplanen antar, på tre punkter, och rapportera
avvikelser till operatören innან `kor-6a`/`kor-1a` dispatchas.

## Checklista

1. **Preview / `current.json`-status (viktigast).** Verifiera mot branchen:
   - Finns `packages/generation/build/immutable_builds.py` med `write_active_pointer`/
     `read_active_build_dir`?
   - Skriver buildern `current.json` med atomär swap på `ok`/`degraded`?
   - Säger `governance/policies/preview-runtime-policy.v1.json` fortfarande StackBlitz
     default (drift mot ADR 0033)? Notera det; lita på ADR 0033 + kod.
   - **Utfall:** om immutable-build/`current.json` saknas → flagga att `kor-7d` är
     blockerad tills Windows-safe-rebuild-pipelinen landat.
2. **current-focus / handoff lurar inte agenten.** Snabbläs båda: stämmer de med faktisk
   HEAD/kodläge? Om de pekar fel (t.ex. påstår att något är klart som inte är det) →
   notera så builder-agenter inte vilseleds. (Uppdatera bara om det är uppenbart och
   säkert; annars rapportera.)
3. **Råtranskript flyttade.** Bekräfta att `real_llm-flow*.txt` ligger under
   `references/raw/` (inte i mappens rot) och är märkta icke-canonical. (Gjort — verifiera.)

## Resultat

En kort **preflight-rapport** till operatören:

| Punkt | Status | Åtgärd |
|-------|--------|--------|
| `current.json`/immutable-build i kod | ja / nej | (om nej: `kor-7d` blockerad) |
| preview-policy-drift | ja / nej | (lita på ADR 0033) |
| current-focus/handoff korrekt | ja / nej | (notera ev. fällor) |
| råtranskript under `references/raw/` | ja / nej | — |

## Separat steward-slice (utanför heavy-flow — blockerar inte 6a/1a)

Coachen flaggade repo-hygien som **inte** ingår i denna mapp men bör tas i en egen slice:

- **Backoffice repo-boundary:** Scaffolds-vyn kan skapa mappar/placeholderfiler under
  `packages/generation/orchestration/scaffolds/<id>/`, vilket krockar med regeln att
  backoffice inte skriver till `packages/`/`apps/`. Egen steward-uppgift.
- **Policy-/status-drift:** `preview-runtime-policy.v1.json` (StackBlitz vs ADR 0033),
  ev. stale `workboard.json`/`known-issues.md`-rader.

Dessa är **inte** blockerare för att börja `kor-6a`/`kor-1a` — notera dem och gå vidare.

## Definition of done

- Preflight-rapporten levererad till operatören.
- Ev. uppenbara docs-fällor noterade (eller säkert korrigerade docs-only).
- Klartecken (eller blockerflagga för `kor-7d`) innan `kor-6a`/`kor-1a` startar.
