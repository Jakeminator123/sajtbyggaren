---
description: Aktivt bug-scope är bara öppna Fix:-open-poster (kör scripts/list_open_bugs.py); bot-/reviewer-fynd verifieras mot remote innan fix; och PR:n körs i en kontrollerad Bugbot-loop.
globs: docs/known-issues.md,.github/**,tests/**
alwaysApply: false
---

# Buggar, PR och reviewerfynd

Konsoliderar bug-scope-disciplin, bot-rapport-verifiering och Bugbot-PR-loopen.

## Bug-scope

`docs/known-issues.md` är kanonisk bugglista och växer monotont (B1, B2, ...). **Aktivt scope = endast buggar med `Fix: open` i "Öppna"-sektionen.** Allt annat (misplaced + stängda) är historik skyddad av regression-test och får inte vara underlag för nytt arbete utan operatörsdirektiv.

Kör som start-steg så scope blir explicit:

```powershell
python scripts/list_open_bugs.py
```

Scriptet skriver fyra kategorier: **Active** (`Fix: open` — scope för nytt arbete), **Misplaced** (har `Fix: <sha>` men ligger kvar i "Öppna" — Steward-städ, inte Builder-scope), **Unknown** (ingen tydlig Fix-marker — operatörs-triage), **Closed** (i "Stängda", skyddad av regression-test).

- Nämner operatörens prompt ett B-ID som inte finns i `Active`: stoppa och fråga (antingen redan stängt, eller `known-issues.md` ur synk).
- "Fixa" en `Misplaced`-bugg = nej, den är redan fixad; flytta posten till "Stängda" (Steward). "Fixa" en `Closed`-bugg = nej, det är en regression; skapa nytt B-ID.

### Format-disciplin i known-issues.md

"Öppna"-poster: `` - **`<ID>` <severity>** - <beskrivning>. ... Fix: open. Test: open. ``
"Stängda"-poster: `` - **`<ID>` <severity>** (stängd <datum>, <sprint>) - <beskrivning>. ... Fix: `<sha>`. Test: `tests/<file>.py::<test>`. ``

Avvikelse gör att `scripts/list_open_bugs.py` failar med `SystemExit` + radnummer. Sammanfattningsraden nära toppen (`> **Aktivt bug-scope:** N aktiva, M misplaced ..., K unknown, L stängda.`) valideras mot scriptets räkning av `tests/test_bug_scope_discipline.py`; bumpa siffrorna i samma commit som en statusändring.

## Bot-/reviewer-verifiering — kolla mot remote, inte mot snippet

När en bot (Bugbot, AI-bug-review, extern reviewer-LLM) eller manuell review flaggar en fil + rad: verifiera ALLTID mot `origin/<branch>:<fil>` innan fix. Bot-tooling cachar ofta filer från första PR-pushen och rapporterar fynd som redan är fixade i senare commits.

```powershell
git fetch origin
git show origin/<branch>:<fil> | Select-String -Pattern "<fix-signatur>" -Context 1
```

Välj `<fix-signatur>` så den matchar fixens unika signatur, inte symptom-mönstret. **Match på remote** = redan fixat → avslå som duplikat (posta gärna "redan fixat i `<SHA>`"), ingen ny commit. **Ingen match** = fyndet stämmer → fixa enligt PR-loopen. Gäller särskilt återkommande fynd om samma funktion och PR:er med 3+ commits efter PR-skapandet. Gäller inte första bot-rapporten på en ny PR eller arkitektur-/designfynd.

## PR-loop (när en PR är öppnad efter operatörs-OK)

1. **Verifiera att Bugbot är aktiverad** direkt efter `gh pr create` (`gh pr view <num> --json statusCheckRollup,reviews,latestReviews`). Är den inte aktiv: rapportera och avbryt loopen, ingen auto-merge utan operatörs-OK.
2. **Polla** i 60-90 s-intervall, max ~8 min, tills `Cursor Bugbot`-checken är `COMPLETED` eller en cursor-review med `BUGBOT_REVIEW` dyker upp.
3. **Tolka resultatet** via tre signaler: Bugbot-checken i `statusCheckRollup`, antalet aktiva (ej-resolvade) inline-fynd via GraphQL `reviewThreads`, och övriga checks (`governance`, `GitGuardian`). Bodyn "found N issues" uppdateras inte mellan commits — läs inte bara bodyn.
4. **Grönt** (Bugbot `SUCCESS`, eller `NEUTRAL` + 0 aktiva inline-fynd, alla övriga checks `SUCCESS`, `mergeStateStatus == CLEAN`, `mergeable == MERGEABLE`): merga med squash, synka arbets-branchen till `main` och kör post-merge-bump.
5. **Rött** → fix-loop, **max 10 iterationer**: fixa minsta möjliga per fynd (ingen scope-utvidgning), kör de fyra guards + tester, commit + push, markera adresserade trådar resolved, polla igen. Vid > 10 iterationer: STOPPA, posta `[NÖDLÄGE PR] Bugbot-loopen avbruten efter 10 fix-iterationer`, lämna PR:n öppen och be operatören besluta.
6. **En PR-loop i taget** (race + rate-limit). Operatören kan alltid avbryta med `stopp`.
