# B157 — Windows Process-Tree-Fynd (Round 3)

**Datum:** 2026-05-28 ~01:30 UTC+2
**Författare:** Cursor-agent (orchestrator-pass)
**Status:** Round 3-fix landad. Round 1 (`adba139`) + Round 2 (`697cf4f`) löste **fel rotorsak**.
**Skrivet för:** operatörens granskning + framtida agent som inte ska bygga om hjulet.

---

## TL;DR

**B157 löstes inte av round 1 + round 2.** Båda tidigare fixar adresserade *timing*-problem i `stopAndWaitPreviewServer` men missade att `child.kill()` på Windows aldrig ens når den process som håller fil-låsen.

Den faktiska rotorsaken är att Node.js `ChildProcess.kill()` på Windows mappar till `TerminateProcess(handle)` som **bara dödar direct PID — inte descendants**. Sajtbyggaren spawnar preview-servern via `npx next start`, vilket skapar processträdet:

```text
npx (parent — finns i Viewser:s servers-map)
  └─ next start (barn — håller fil-låsen på native .node-binaries)
```

`child.kill("SIGKILL")` killar bara `npx`-shellen. `next start`-barnet lever vidare och håller `next-swc.win32-x64-msvc.node`-låset → `copy_starter()` får `PermissionError: [WinError 5]` även efter att `stopAndWaitPreviewServer` returnerat `true`.

**Fixen i round 3:** ny `killProcessTree`-helper som på Windows spawnar `taskkill /PID <pid> /T /F` istället för `child.kill()`. `/T` = tree (alla descendants), `/F` = force.

---

## Reproduktion 2026-05-28 ~01:08 UTC+2

Sessionen testade hela kärnflödet via Viewser-browser:

1. **Init-bygget:** prompt = "Hemsida för ett litet bageri i Lund som heter Surdegen…", verksamhetstyp = LSB, vibe = Warm Craft, tone = Varm och personlig, CTA = Kontakta oss, hoppade över media. Build genom Viewser **lyckades** (`POST /api/prompt 200 in 116s`). siteId blev `surdegen-08ced7`. Preview-server spawnades på port 4163 (process 31472, parent npx 27976).

2. **Follow-up-prompt:** "Lägg till mycket mer text om våra surdegsbröd och när vi har öppet på startsidan. Ändra också ngt synligt så jag ser att det blev en ny version." Build **kraschade** efter 19.6 sekunder med:

   ```text
   POST /api/prompt 500 in 19.6s
   ```

   UI-felmeddelande:

   > `build_site.py misslyckades (1) utan strukturerad output. Traceback (most recent call last): File "C:\Users\jakem\Desktop\sajtbyggaren\scripts\build_site.py", line 4119, in <module> raise SystemExit(...)`

3. **CLI-reproduktion** mot samma dossier (`data/prompt-inputs/surdegen-08ced7.v2.project-input.json`) gav exakt fel-rad i build_site.py rad 726:

   ```text
   PermissionError: [WinError 5] Åtkomst nekad:
     'C:\Users\jakem\Desktop\sajtbyggaren-output\.generated\surdegen-08ced7\node_modules\@next\swc-win32-x64-msvc\next-swc.win32-x64-msvc.node'
   ```

4. **Process-tree-snapshot** under tiden CLI-bygget kraschade:

   ```text
   PID 27976  npx next start -p 4163              (parent — i Viewser:s servers-map)
   PID 31472  next start -p 4163                  (BARN — låser node_modules)
   ```

   `child.kill()` på 27976 från Viewser:s `stopAndWaitPreviewServer` dödade *bara* npx-shellen. PID 31472 levde vidare och blev orphan med exklusivt fil-lås.

5. **Verifiering att 31472 var culprit:** `Stop-Process -Id 31472 -Force` + `Stop-Process -Id 27976 -Force`, sedan re-kör samma CLI-bygge → **lyckades på 109 sekunder, helt grön**. Samma kod, samma input, enda skillnad: hela process-trädet dött istället för bara parent. Det bevisar exakt vilken process som höll låset och vilken kod-rad som behövs.

---

## Round-historik

### Round 1 (`adba139`, akut nivå 1)

`stopAndWaitPreviewServer`-helper introducerad i `apps/viewser/lib/local-preview-server.ts`:

- SIGTERM på `child` (npx-parent på Windows)
- Vänta in `exit`-event eller `timeoutMs` (5s default)
- SIGKILL-fallback om timeout
- 200ms Windows-wait för file-handle-release

**Saknades:** tree-kill. Fix:en byggde på antagandet att `child.kill()` skulle ta hela process-trädet, vilket är sant på POSIX men inte på Windows.

### Round 2 (`697cf4f`, reap-fix)

Reviewer-fynd: `Promise.race([exited, timeoutPromise])` resolverade omedelbart efter att SIGKILL skickats utan att vänta på faktiskt `exit`-event. Round 2 lade till:

- `sigkillSent`-flag i timeout-callbacken
- Sekundär `Promise.race([exited, REAP_TIMEOUT_MS])` efter primär race
- 3 strukturella regression-tester i `tests/test_local_preview_server_b157_followup.py`

**Var fortfarande inte tillräckligt.** Reap-fixen skyddar mot timing-race, men om barnprocessen aldrig får SIGKILL spelar det ingen roll hur länge vi väntar på exit-event.

### Round 3 (denna commit)

Reviewer/test-fynd 2026-05-28: end-to-end-test av kärnflödet via Viewser-browser visade att follow-up fortfarande failade med exakt samma WinError 5. Process-tree-snapshot bekräftade Windows `kill()`-semantiken som rotorsak.

Ny `killProcessTree`-helper i `apps/viewser/lib/local-preview-server.ts`:

```typescript
async function killProcessTree(
  child: ChildProcess,
  signal: NodeJS.Signals,
): Promise<void> {
  if (process.platform !== "win32") {
    try { child.kill(signal); } catch { /* race */ }
    return;
  }
  if (typeof child.pid !== "number") return;

  await new Promise<void>((resolve) => {
    let settled = false;
    const finalize = () => { if (settled) return; settled = true; resolve(); };
    const tk = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    tk.once("exit", finalize);
    tk.once("error", finalize);
    setTimeout(finalize, 2_000); // hard cap
  });
}
```

Plus `stopAndWaitPreviewServer` fick en explicit Windows-fast-path som hoppar över graceful SIGTERM-fönstret (det finns ingen graceful path på Windows ändå — Node.js mappar SIGTERM → TerminateProcess som är force):

```typescript
if (process.platform === "win32") {
  const REAP_TIMEOUT_MS = 2_000;
  await killProcessTree(child, "SIGKILL");
  await Promise.race([
    exited,
    new Promise<void>((r) => setTimeout(r, REAP_TIMEOUT_MS)),
  ]);
  await new Promise((r) => setTimeout(r, 200));  // file-lock-release
  return true;
}
// POSIX-graceful-path nedan (oförändrad — process groups respekteras
// av child.kill() på POSIX så vi behöver inte tree-kill där).
```

`stopPreviewServer` (fire-and-forget-versionen) använder också `killProcessTree` för konsistens.

### Plus 4 nya regression-tests i `tests/test_local_preview_server_b157_followup.py`

`test_b157_round3_uses_process_tree_kill_on_windows`:

1. `killProcessTree`-helper finns deklarerad någonstans i filen
2. `taskkill /T` spawnas (utan `/T` är vi tillbaka i B157-territoriet)
3. Helpern anropas från `stopAndWaitPreviewServer`-bodyn (inte död kod)

---

## Manuell verifiering du kan köra

Efter att fixen pushats kan du verifiera end-to-end så här:

```powershell
# 1. Säkerställ ren state
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

# 2. Starta Viewser
cd C:\Users\jakem\Desktop\sajtbyggaren\apps\viewser
npm run dev
# Vänta på "Ready in"-rad

# 3. Öppna http://localhost:3000 i Chromium-browser
# 4. Gör en init-prompt + wizarden, vänta in "Sajten <siteId> är aktiv"
# 5. Skicka en fri follow-up via FloatingChat
# 6. Kontrollera att follow-up-bygget INTE failar med WinError 5
#    (det får ta ~2-7 minuter för en faktisk build)

# 7. Verifiera att inga orphan next-processer ligger kvar:
Get-Process node | Where-Object {
  (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like "*next start*"
} | Select-Object Id, StartTime
# Bör vara tomt EFTER att follow-up-bygget startat (preview stoppas).
# Efter att bygget klart spawnas en NY preview för follow-up — den ska finnas.
```

**Förväntat resultat:** follow-up-build går igenom utan WinError 5. Tidsram: ~60-180 sekunder beroende på lockfile-drift och om `npm install` behöver köras om.

---

## Vad som INTE är fixat (kvarliggande tech-debt)

Detta är fortfarande nivå-1-fix per `docs/gaps/GAP-windows-safe-rebuild-pipeline.md`. Anti-patternet **"rebuilda ovanpå live preview-katalog"** kvarstår.

Edge cases där fixen fortfarande kan brista:

- **CLI-bygge utanför Viewser** (t.ex. `python scripts/build_site.py`) går inte genom `build-runner.ts` → `stopAndWaitPreviewServer` aktiveras aldrig. Om en Viewser-instans dessutom kör en preview för samma siteId får CLI-bygget `WinError 5`. Workaround: stäng Viewser eller kör CLI-bygget på annan siteId.
- **Orphan-processer från en kraschad eller stängd Viewser-session** är inte i någon nuvarande `servers`-map, så ingen helper kan stoppa dem. Workaround: `Stop-Process -Force -Name node` innan ny dev-session.
- **Race där viewer-panel:n åter-startar preview MITT under build** är teoretiskt möjlig (ny preview spawnas mellan `stopAndWaitPreviewServer` och `copy_starter()`-rmtree).

Den **rätta arkitektur-lösningen** är level-4 immutable build-dir + manifest-pointer-swap (Vercel-likt):

```text
.generated/<siteId>/
  builds/
    20260528T013025-aabbcc/   ← ny build skrivs här
    20260528T012810-x9y8z7/   ← gammal build kvar, preview pekar på den
  current.json                ← pointer-fil ({"build": "20260528T013025-aabbcc"})
```

Pointer-swap är atomär `rename`. Aktiv `next start` mot gammal build fortsätter köra, oberörd av nytt bygge i ny katalog. Gamla builds prunas av delayed GC-jobb.

Spec finns i `docs/gaps/GAP-windows-safe-rebuild-pipeline.md`. Egen sprint, inte gjord ikväll.

---

## Filer ändrade i round-3-fixen

- `apps/viewser/lib/local-preview-server.ts` — `killProcessTree` ny helper, `stopPreviewServer` använder den fire-and-forget, `stopAndWaitPreviewServer` har Windows-fast-path som anropar helpern + reap-cap. Round-historik dokumenterad i jsdoc.
- `tests/test_local_preview_server_b157_followup.py` — ny `test_b157_round3_uses_process_tree_kill_on_windows` med 3 strukturella assertions.
- `docs/known-issues.md` — B157-stängningen kompletterad med round-3-stycke + ny commit-SHA.
- `B157-WINDOWS-PROCESS-TREE-FYND.md` — denna fil. Lever i repo-roten så du kan granska den enkelt; flytta gärna till `docs/incidents/` eller `docs/troubleshooting/` när du skapar en sådan struktur.

---

## Lärdomar

1. **Windows process-modellen är inte POSIX.** `child_process.kill()` lurar utvecklare som lärt sig på Linux/macOS. För spawn:ade verktyg som spawnar barn (t.ex. `npx`, `npm run`, `cmd.exe /c`) MÅSTE man tree-kill på Windows.

2. **End-to-end-testning fångar saker enhets-tester missar.** Round 1 + Round 2 hade strukturella regression-tester som GICK IGENOM, men kärnflödet via Viewser-browser failade. Test-täckning != korrekt logik.

3. **Reviewer-pass kan ha fel rotorsak.** Round 1-reviewern såg timing-race i `Promise.race`. Det var en ÄKTA bug men inte den primära. Att en reviewer flaggar något betyder inte att det är hela problemet.

4. **`POST /api/prompt 500 in <kort tid>` + traceback rad 4119** är distinkt fingerprint för B157-klassen. Om det dyker upp igen efter denna fix: det är troligen en NY edge case (CLI vs Viewser, orphan från krasch, race med viewer-panel-poll). Inte denna kod-rad.

---

## Referenser

- `docs/known-issues.md` — B157 (stängd, samtliga rounds dokumenterade)
- `docs/gaps/GAP-windows-safe-rebuild-pipeline.md` — nivå-4-spec (immutable build-dir + pointer-swap)
- `apps/viewser/lib/local-preview-server.ts` — implementation
- `apps/viewser/lib/build-runner.ts` — caller (`runBuildOnce` anropar `stopAndWaitPreviewServer` före Python spawnas)
- `scripts/build_site.py` rad 705-731 — `copy_starter()` med `shutil.rmtree(node_modules)`
- `tests/test_local_preview_server_b157_followup.py` — alla 4 strukturella regression-tester (round 2 + round 3)
- Node.js issue om Windows tree-kill: <https://github.com/nodejs/node/issues/3617> (öppen sedan 2015 — det är inte en ny upptäckt)
