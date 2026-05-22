# Team Workflow

Milestone: Team Parallel Work v1.

Den här arbetsmodellen ska göra det lättare för två personer att bygga
parallellt utan att göra dokumentation till ett självändamål. Dokumenten här
ska hjälpa bygget: när de inte hjälper ska de förenklas.

## North Star

Sajtbyggaren ska vinna genom kärnloopen:

```text
prompt -> företagshemsida -> preview -> följdprompt -> ny version
```

All arbetsdelning ska stödja den loopen.

## Teammodell

- Jakob äger ungefär 75% av arbetet: backend, generation, orchestration,
  governance, evals och produktbeslut.
- Frontend-medutvecklaren äger ungefär 25% av arbetet: Viewser, preview shell,
  design, UX, mockade UI-flöden och frontend-polish.
- Båda kan reviewa varandra.
- Roller är riktlinjer, inte låsta lagar. Om en ändring korsar gränsen ska
  den göras tydlig i PR-beskrivning och handoff.

## Contract-first

Frontend ska inte behöva vänta på att all backend är klar.

- Skapa gemensamt datakontrakt först när frontend och backend möts.
- Skapa mock-data tidigt så frontend kan bygga UI mot realistiska states.
- Backend implementerar sedan riktig data bakom samma kontrakt.
- Backend får inte ändra ett shared contract tyst.
- Frontend får inte bygga runt gissade API-shapes utan att dokumentera dem i
  `docs/contracts/`.
- När kontraktet ändras ska PR:en säga vilken frontend- och backend-yta som
  påverkas.

## Branchmodell

Använd tydliga branch-prefix när operatören ber om PR- eller branchflöde:

- `backend/<kort-namn>`
- `frontend/<kort-namn>`
- `contract/<kort-namn>`
- `docs/<kort-namn>`
- `scout/<kort-namn>` eller `review/<kort-namn>`

Repo:t kan fortfarande använda direkt-main-flöde när operatören uttryckligen
väljer det. Större eller osäkra ändringar ska gå via branch/PR.

## Konfliktregel

- Två personer eller agenter ska inte jobba i samma branch samtidigt.
- Två personer eller agenter ska inte ändra samma filer samtidigt.
- Om båda behöver samma fil: pausa och gör en liten contract-PR först.
- Vid osäker ägargräns: läs `docs/ownership-map.md`, stoppa om konflikten
  kvarstår och rapportera.

## PR-regel

- Frontend feature -> PR.
- Backend/generation logic -> PR.
- Shared contract -> liten separat PR när möjligt.
- Låg-risk docs kan gå snabbare, men ska fortfarande rapporteras tydligt.
- PR ska säga vad som ändrades, vilka contracts som berörs och vilka ytor som
  uttryckligen inte rördes.

## Praktisk ordning

1. Identifiera om arbetet är frontend, backend, shared contract eller docs.
2. Läs ägarkartan.
3. Skapa eller uppdatera contract/mocks om gränsen är gemensam.
4. Bygg smalt inom ägarens yta.
5. Låt andra rollen reviewa när ytan korsar frontend/backend-gränsen.
