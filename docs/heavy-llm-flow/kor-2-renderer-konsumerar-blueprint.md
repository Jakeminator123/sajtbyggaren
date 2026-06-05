# KÖR 2 — Renderer konsumerar blueprint

**Profil:** [`04-builder-profil.md`](04-builder-profil.md).
**Läs först:** [`01-artefakt-kontrakt-blueprint.md`](01-artefakt-kontrakt-blueprint.md) §4, §6,
[`00-malbild-och-lager.md`](00-malbild-och-lager.md) §2.
**Beror på:** `kor-1c`.

---

## Mål

Låt de deterministiska renderern läsa `contentBlocks` + `visualDirection` från
Generation Package i stället för generiska mall-defaults — för de fält som märks
direkt. Målet är inte hela systemet; det är att den första generationen ska gå från
~5/10 till ~8/10 upplevd finish.

## Varför

Idag är copy generisk oavsett bransch (samma story/tagline/FAQ-mall). Det är här "den
generiska känslan ska dö". Renderern är säker och stabil — vi byter bara **innehålls-
källan** från mall-defaults till blueprint, med oförändrad fallback.

## Scope (fält som ska konsumeras först)

```text
contentBlocks.<route>.hero.headline / subheadline / proofLine / primaryCta
contentBlocks.services.service-list[]  (title, summary, bullets)
contentBlocks.<route>.story
contentBlocks.<route>.faq[]
site-brief trustSignals / businessFacts  -> trust-proof-sektionen
visualDirection.heroStyle / density      (lätt påverkan; full mapping i kor-3b)
```

## Filer

- `packages/generation/build/renderers.py` (hero, service-list, story, faq, trust-proof,
  contact-cta läser blueprint med graceful fallback till nuvarande mall)
- `packages/generation/build/dispatcher.py` (skicka blueprint-data till section-renderers)
- ev. `scripts/build_site.py` (tråda igenom Generation Package till render-anropet)
- `tests/` (render-tester per bransch)

**Off-limits:** schema-ändringar (gjordes i `kor-1a`), preview/adaptrar, viewser-UI,
full visual-direction-mapping (det är `kor-3b`), fri kodgenerering.

## Konkret arbete

1. Renderern tar emot Generation Package (eller en härledd render-input) och läser
   `contentBlocks.<route>.<section>` per sektion. Saknas blueprint-fält → behåll
   nuvarande deterministiska mall (ingen regression).
2. Hero: använd `headline/subheadline/proofLine/primaryCta`. Services: rendera flera
   konkreta tjänster från `service-list`. Story/FAQ: branschnära innehåll från blueprint.
3. Trust-proof: rendera **bara** signaler som finns i `businessFacts`/`trustSignals` —
   respektera `unknowns`/`qualityRisks` (ingen fake-cert, ingen placeholder-kontakt).
4. CTA följer `conversion.primaryCta`/`ctaRules` (visa inte telefon om den saknas).

## Testfall (DoD)

- Elektriker, frisör, naprapat och keramik-e-handel renderas som **fyra olika
  företagstyper** — inte samma mall med utbytta ord (jämför hero, services, story, FAQ).
- Trust-proof visar inga ogrundade claims.
- Saknad blueprint → identisk output mot dagens mall (regressionsskydd).
- `appliedVisibleEffect` blir `true` när blueprint faktiskt ändrar renderad output.
- Scope-relevanta checks gröna (se builderprofilen §5). Denna skiva rör renderern brett
  → kör **full** `pytest tests/ -q`.

## Checks (scope-baserat)

`git diff --stat` · `ruff` på `packages/generation/build` + `scripts` · render-pytest per
bransch · **full** `pytest tests/ -q` (renderern rörs brett).

## Prompt till builder-agenten

```text
Du ar builder-agent i Sajtbyggaren. Folj docs/heavy-llm-flow/04-builder-profil.md.
Uppgift: KOR 2 - lat renderern konsumera contentBlocks/visualDirection fran
Generation Package (KOR 1c) for hero/services/story/faq/trust/CTA.

Krav:
- Graceful fallback: saknas blueprint-falt -> nuvarande deterministiska mall (0 regress).
- Respektera arlighet: rendera inga claims/kontaktvagar som ligger i unknowns/qualityRisks.
- CTA foljer conversion.primaryCta/ctaRules.
- Ror inte scheman (KOR 1a), preview/adaptrar, viewser-UI eller full visual mapping (KOR 3b).

Definition of done: de fyra baseline-branscherna ser tydligt olika ut (hero/services/
story/faq), inga ogrundade claims, saknad blueprint ger identisk output mot dagens mall,
appliedVisibleEffect=true vid faktisk andring, full pytest + ruff grona.
```
