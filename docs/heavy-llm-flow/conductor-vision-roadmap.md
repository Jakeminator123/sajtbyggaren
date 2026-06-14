# Konduktör-roadmap — operatörens vision (read-only underlag)

> Framtaget 2026-06-14 (takeover-prep-rundan) som read-only underlag. Detta är
> en riktningskarta, inte en byggd funktion — verifiera alltid mot git/koden.
> Djupare arkitekturplan: [`openclaw-2.0-conductor.md`](openclaw-2.0-conductor.md).
> Aktuell köplan: [`../current-focus.md`](../current-focus.md).

## Visionen

Operatörens mål: en fri, kreativ följdprompt ska kunna gå hela vägen genom
loopen `prompt -> analys -> npm -> generativ komponent -> montering -> ny
version`. Det kanoniska exemplet är "lägg en roterande 3D-pizza ovanför
headern" — alltså en helt ny, icke förkatalogiserad komponent som konduktorn
förstår, hämtar/bygger beroenden för, genererar, monterar och visar i nästa
preview-version.

## Var vi står idag (ärligt)

Visionen är arkitekturellt förankrad men **ej byggd**. Dagens konduktor är en
ärlig, regelbaserad router som väljer mellan fyra begränsade roller och en
femte partiell roll, och som applicerar allt genom den deterministiska
apply-kedjan med guards (KÖR-7) — aldrig fri filpatch.

- Roller idag: `router`, `section_builder`, `stylist`, `copy` (kockarna) plus
  en partiell `component_builder` (ADR 0057, mount-only/partial — den kan
  beskriva en komponent men monterar den inte som en stödd förmåga ännu).
- Sedan #316 landar restyle (färg/typsnitt) via tema-utföraren och stylist-
  rollen; det är den senaste rollen som gick från tyst no-op till ärligt
  applicerad.

En pizza-prompt når alltså inte fram: den fastnar i `classify_message` som
unclear, eller — om den tar sig förbi klassningen — faller senare som
plan_rejected (ingen mappad förmåga i capability-map) eller apply_unmapped
(ingen apply-väg för intentet). Det är ärligt: systemet låtsas inte bygga
något det inte kan.

## Stegtrappa mot visionen

Varje steg är självständigt levererbart och flyttar gränsen för vad en fri
prompt kan åstadkomma. Storlek är grov (M/L/XL).

| Steg | Vad | Storlek |
|---|---|---|
| 1 | katalog-mount: låt `component_builder` gå partiell -> stödd mount för komponenter som redan finns i katalogen/capability-map (samma apply/mount-maskineri som faq/contact-form). Ärligt mot #313. Kräver ADR-utökning av 0057. | M |
| 2 | kuraterat 3D-recept: en förgranskad, beroende-pinnad komponent (t.ex. en 3D-yta) som ett kuraterat intag, monterbar via steg 1:s maskineri. | L |
| 3 | novel-intent planeringssvar: när intentet är okänt, svara med en ärlig plan ("så här skulle det kunna byggas") i stället för en tyst unclear. | M |
| 4 | prompt -> dossier-inferens: härled en strukturerad dossier/förmåga ur fri prompt så fler intent kan mappas utan handpåläggning. | L |
| 5 | generativ komponent-agent: en roll som faktiskt genererar ny komponentkod (med npm-beroenden) inom guards. Detta är pizzans kärna. | XL |
| 6 | extern Docker-konduktor: flytta konduktorn till en fristående tjänst (openclaw-2.0-conductor fas 3) som Viewser chattar med över HTTP. | L |

Hela pizza-visionen (steg 5 fullt ut) är ett arkitekturprogram över månader,
inte en enskild skiva. Rekommenderad första byggskiva är **steg 1** — den ger
synligt värde, återanvänder befintligt maskineri och håller ärlighetslinjen
från #313.

## Princip som inte får brytas

Frihet i förståelsen (LLM-roller får tolka fri prompt), kontroll i
appliceringen (deterministisk apply + guards + immutabla versioner). Rollerna
*förstår och föreslår*; den deterministiska kedjan *validerar och applicerar*.
Ingen roll patchar filer fritt och ingen roll blir en parallell sanningskälla.
