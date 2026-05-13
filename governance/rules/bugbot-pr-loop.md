---
description: När en PR är öppen, polla Bugbot upp till 8 minuter och kör fix-loop max 10 iterationer innan eskalering till operatör som "nödläge PR".
alwaysApply: true
---

# Bugbot PR-loop

Den här regeln gäller när en PR har öppnats (efter operatörens
uttryckliga instruktion enligt `branch-discipline.md`). När PR finns
kör agenten loopen nedan automatiskt utan att fråga operatör för
varje steg, **fram tills** ett av två stopp-villkor (allt grönt =
merge, eller > 10 iterationer = nödläge).

## 1. Verifiera att Bugbot faktiskt är aktiverad på PR:n

Direkt efter `gh pr create`:

1. Hämta PR-status:
   ```
   gh pr view <num> --json statusCheckRollup,reviews,latestReviews
   ```
2. Bugbot räknas som aktiverad om något av följande dyker upp i
   svaret:
   - En check med `name == "Cursor Bugbot"` i `statusCheckRollup`.
   - En review med `author.login == "cursor"` i `reviews` eller
     `latestReviews`.
3. Om aktiverad: skriv exakt strängen
   `kommer nu vänta i upp till högst 8 min på att bugbotten blir klar`
   till operatören som första rad i nästa svar, så hen vet att
   loopen tar tid utan att behöva fråga.
4. Om INTE aktiverad: posta en kort statusrad till operatören
   (`Bugbot är inte aktiv på denna PR; lämnar till operatör för
   manuell review`) och avbryt loopen. Inga `gh pr merge`-anrop
   utan operatör-OK när Bugbot saknas.

## 2. Polla Bugbot upp till 8 minuter

Polla i intervaller om 60–90 sekunder. Sammanlagt max 480 000 ms
(8 min) räknat från första polling-anrop. Avbryt poll så fort
ett av följande inträffar:

- `Cursor Bugbot`-checken i `statusCheckRollup` har
  `status == "COMPLETED"` (oavsett `conclusion`).
- En review från `author.login == "cursor"` dyker upp där `body`
  innehåller `BUGBOT_REVIEW`.

Om 8 min passeras utan resultat: stoppa loopen, rapportera till
operatör att Bugbot inte slutförde inom tidsfönstret. Operatör
beslutar nästa steg.

## 3. Tolka Bugbot-resultatet

Två signaler räknas:

- Bugbot-reviewens body innehåller `found 0 potential issues` eller
  motsvarande "no issues"-formulering, **eller**
  `Cursor Bugbot`-checken har `conclusion == "SUCCESS"` →
  räknas som **grönt**.
- Bodyn säger `found N potential issues` med N ≥ 1, eller
  `conclusion == "FAILURE"` på checken → räknas som **rött**.
  Hämta inline-kommentarerna för att se de konkreta fynden:
  ```
  gh api repos/<owner>/<repo>/pulls/<num>/comments
  ```

`conclusion == "NEUTRAL"` på checken är typiskt det Bugbot
postar tillsammans med inline-fynd; tolka då efter bodyn ("found N
potential issues") snarare än efter check-conclusion.

## 4. Grönt → merge automatiskt

Om Bugbot är grön OCH alla övriga checks i `statusCheckRollup`
(t.ex. `governance`, `GitGuardian`) har `conclusion == "SUCCESS"`
OCH `mergeStateStatus == "CLEAN"` OCH `mergeable == "MERGEABLE"`:

1. `gh pr merge <num> --squash --delete-branch`.
2. `git checkout main && git pull --ff-only origin main`.
3. Ta bort lokal feature-branch om kvar (`git branch -d <branch>`).
4. Kör Standard loop steg 7 som mainline-steward-commit på `main`:
   bumpa `Last verified`-SHA i `docs/current-focus.md`, uppdatera
   Queue / Stage / Next action, och flytta ev. stängda B-IDs till
   "Stängda - regression-test säkrar fixet"-sektionen i
   `docs/known-issues.md` med squash-merge-SHA.

Auto-merge i steg 1 kräver ingen ny operatörs-prompt eftersom den
här regeln själv är operatörens explicit-givna mandat för PR-
loopen. Operatör kan alltid avbryta genom att skriva `stopp`.

## 5. Rött → fix-loop, max 10 iterationer

Räkna iterationer från och med första Bugbot-rödt-svar (iteration 1).
Per iteration:

1. Läs alla inline-kommentarer från Bugbot. Sortera efter allvar
   (`High` → `Medium` → `Low`).
2. Implementera minsta möjliga fix per fynd. Ingen sido-städning,
   ingen scope-utvidgning.
3. Kör de fyra guards lokalt + relevanta tester. Allt ska vara
   grönt innan push.
4. Commit + push till samma feature-branch (varje push triggar ny
   Bugbot-runda).
5. Återgå till steg 2 i denna regel (polla 8 min).

Om iterationsräknaren skulle bli > 10:

- STOPPA loopen direkt. Posta en kommentar på PR:n med titeln
  `[NÖDLÄGE PR] Bugbot-loopen avbruten efter 10 fix-iterationer`
  och kort beskrivning av återstående fynd.
- Lämna PR:n öppen utan att merga.
- Rapportera till operatör att Bugbot-loopen avbrutits och be om
  beslut: stäng + omplanera, accept resterande fynd och merge
  manuellt, eller dela upp i mindre PR:er.

## 6. En PR-loop i taget

Agenten kör Bugbot-loopen för **en** PR i taget. Två parallella
loopar är inte tillåtna (race-villkor + Bugbot rate-limit-risk).
Om operatör ber om en ny PR medan en loop pågår: avsluta nuvarande
loop (merge eller nödläge) före nästa PR öppnas.

## 7. Cross-references

- `.cursor/BUGBOT.md` — vad Bugbot själv kollar efter (review-
  reglerna är inte denna regels scope).
- `governance/rules/branch-discipline.md` — när en PR
  överhuvudtaget får skapas (operatör-OK krävs).
- `docs/agent-handbook.md` Standard loop steg 2 + 6 + 7 — denna
  regel är operationaliseringen av steg 2 (Ro-review = Bugbot på
  PR), steg 6 (merge) och steg 7 (post-merge bump) för PR-flödet.
