---
status: active
owner: governance
truth_level: source
last_verified_commit: f56ac30
---

# docs/archive — arkivregler

Den här mappen är **historik**. Filer som flyttas hit har spelat ut sin roll
som aktiv köplan/diagnos men bevaras för spårbarhet (princip: *flytta, radera
aldrig*). Underkataloger grupperar per datum eller städpass
(`2026-05-19/`, `2026-05-27/`, `2026-06/`, …).

## Sanningskälla vs arkiv

- **Sanningskällan för nuläget** är `docs/current-focus.md` (aktuell köplan) +
  toppblocket i `docs/handoff.md` (senaste överlämning). Maskinläsbara kontrakt
  bor i `governance/policies/` + `governance/schemas/`.
- **Arkiverade filer är inte sanningskälla.** De beskriver ett historiskt läge
  vid en viss tidpunkt. SHA:n, statusrader och "nästa steg" i arkivet är
  ögonblicksbilder och ofta inaktuella.
- **Arkivet får aldrig användas som aktuell köplan.** Läser du ett arkiverat
  dokument: verifiera alltid mot git/koden och mot `current-focus.md`, aldrig
  mot det arkiverade blocket.

## Hur en fil arkiveras

1. Flytta med `git mv` så `git log --follow <fil>` ser hela historiken.
2. Lägg en kort frontmatter/not i toppen på den flyttade filen:
   `status: historical` (eller `superseded`) + en rad
   "superseded av `<current-focus.md / handoff.md / ADR / efterföljande doc>`".
3. Notera flytten i mappens `README.md` (datum-katalogens index).

## Frontmatter-konvention (aktiva docs)

Stora aktiva docs bär en frontmatter-header så läsaren snabbt ser status och
ägarskap:

```
status: active | active-plan | historical | superseded
owner: backend | ui | governance | infra
truth_level: source | summary | historical-reference
last_verified_commit: <sha eller unknown>
```

`truth_level: source` = filen (eller dess länkade policy) är sanningskälla;
`summary` = sammanfattar en källa på annan plats; `historical-reference` =
bevaras som historik, inte aktuell sanning.
