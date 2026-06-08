# Lane B — FloatingChat-split (Builder, UI, cloud)

> **FÖRBEREDD LANE — starta manuellt, kräver operatörs-OK.** Detta rör
> Christophers UI-lane (`apps/viewser/**`) och är en **refaktor, inte en
> buggfix** → det stående jakob-be-grant:et räcker INTE; operatören måste säga
> OK och informera Christopher innan start. Klistra in hela meddelandet som
> första prompt i en Cursor Cloud Agent. Disjunkt write-set mot lane A/C och
> det lokala backend-arbetet.

---

Du arbetar i `Jakeminator123/sajtbyggaren` på branch **`christopher`** (eller en
feature-branch `frontend/floating-chat-split` med avstamp från `christopher`).

Setup (Ubuntu cloud-VM) — **egen feature-branch så lanes kan köra parallellt**:
```bash
git switch christopher && git pull origin christopher
git switch -c frontend/floating-chat-split
cd apps/viewser && npm install
```
Stoppa direkt med felmeddelande om setup misslyckas.

**Roll:** Builder (UI). **Scope:** dela upp den 2 764 rader stora
`apps/viewser/components/builder/floating-chat.tsx` i mindre filer **bredvid**
den. **STRIKT behavior-preserving** (refaktor som inte ändrar beteende, bara
struktur).

Läs först: `AGENTS.md`, `docs/current-focus.md`, `docs/handoff.md` (topp-blocket),
`docs/ownership-map.md`, `governance/rules/branch-discipline.md`,
`apps/viewser/components/builder/floating-chat.tsx` (hela filen).

## Uppgift
1. Identifiera naturliga sömmar i `floating-chat.tsx`: t.ex. typer/interfaces,
   rena hjälpfunktioner, sub-komponenter, hooks (`useFollowup*`), och
   presentational delar.
2. Extrahera dem till nya syskonfiler, t.ex. en mapp
   `apps/viewser/components/builder/floating-chat/` med `types.ts`, `hooks.ts`,
   `helpers.ts` och mindre `*.tsx`-delkomponenter. Behåll
   `floating-chat.tsx` (eller `floating-chat/index.tsx`) som tunn
   sammansättning med **oförändrad publik export och oförändrat beteende**.
3. Inga ändringar i logik, props-kontrakt, nät-anrop eller UX. Ren mekanisk
   extraktion + imports. Om du upptäcker en bugg: notera den i rapporten, fixa
   den INTE i denna refaktor (separat lane).

## Off-limits (rör inte)
`apps/viewser/app/api/prompt/**` och all annan `/api/`-route, all Python
(`scripts/**`, `packages/**`), alla data-/run-kontrakt, `lib/openclaw-runner.ts`
beteende. Ändra inga tester så att de döljer beteendeskillnader. Öppna ingen PR.

## Verifiering (alla gröna före push)
```bash
cd apps/viewser
npm run lint
npx tsc --noEmit          # eller projektets typecheck-script
npm run build
```
Beteende-bevis: beskriv i rapporten att publik export är oförändrad och att
inga props/▸händelser ändrats (diffen ska vara flytt + import, inte logik).

## Stoppa om
Du inte kan hålla extraktionen behavior-preserving, typecheck/build failar,
scope växer utanför `floating-chat*`, eller `origin/christopher` har rört sig.

## Leverans (tillfällig branch — egen feature-branch för UI-lanen)
Pusha feature-branchen (den kan köra parallellt med A och C eftersom den är en
egen branch):
```bash
git push -u origin frontend/floating-chat-split
```
Säg till operatören att lanen är klar. Eftersom detta är Christophers lane bör
ändringen **reviewas av operatören/Christopher** innan den mergas in i
`christopher` — en PR mot `christopher` rekommenderas just för review (men det är
operatörens val). Lista alla nya/ändrade filer i rapporten. Öppna INGEN PR mot `main`.

## Slutrapport (exakt format)
```
Branch pushad: frontend/floating-chat-split (redo för review/merge in i
christopher). UI-typecheck + lint + build gröna. Behavior-preserving: publik
export oförändrad, inga kontraktsändringar. Nya filer: <lista>. Ev. noterade
buggar (ej fixade): <lista eller "inga">. Klar — vänta operatörens nästa instruktion.
```
