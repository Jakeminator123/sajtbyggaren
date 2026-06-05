# Arkiverade gap-filer

Avslutade gap-filer flyttas hit för att hålla `docs/gaps/` rent och för att
`list_gaps` (som globbar `docs/gaps/*.md` icke-rekursivt) inte ska visa
färdiga gap som om de vore köade.

- Statusen i en gap-fils frontmatter är ögonblicksbilden vid skapandet och är
  ofta inaktuell. Den auktoritativa livscykeln finns i `docs/workboard.json`
  (`completedGaps`). Det är därför filer här kan stå som `status: queued` trots
  att arbetet är klart och mergat.
- Aktiva/köade gap ligger kvar en nivå upp i `docs/gaps/`.

Flytta tillbaka en fil till `docs/gaps/` om ett arkiverat gap återöppnas.
